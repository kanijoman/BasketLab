// «Mi equipo» of BasketLab Talent (epic #872, C1 #882): the squad of a team, where its game has holes and the search that would fill each one, as plain functions (no React, no network).
//
// Rules that were decided (20/11/2026):
//  - the staff CHOOSES the team (any competition and season published, senior or youth); where it is remembered is the page's business (the address first, then the browser);
//  - the rotation is who played enough (`eligible`: 10 minutes a game, a third of the games of the team, 3 games); the rest is the bench;
//  - a hole is a matter of PLAYING PROFILE, not of position (three centres and nobody who rebounds is a hole in rebounding): an axis of the radar that NOBODY in the rotation covers, that is, the best
//    player of the rotation does not reach the percentile `COVER_PCT` (75) in it, in HIS competition. It is the best, not the mean: one rebounder covers rebounding however weak the others are;
//    it is only said when the rotation has `MIN_ROTATION` players and `MIN_WITH_AXIS` of them have the figure;
//  - the position (bases and guards, wings, centres) is information, never a hole; the age too (share of the minutes of the under 22 and the 30 or over);
//  - the suggestion is a search already filled in (`SUGGEST_PCT` percentile in the axis nobody covers, with minutes enough): no ranking of its own.
import { RADAR_AXES } from './player'
import { filtersToParams, NO_FILTERS, POSITION_GROUPS, type PositionGroup, type SearchFilters, type SearchRow } from './search'

export const MIN_ROTATION = 5
export const COVER_PCT = 75                // the best of the rotation must reach it in an axis for the axis to be covered
export const SUGGEST_PCT = 75
export const AGE_YOUNG = 22
export const AGE_VETERAN = 30
const MIN_WITH_AXIS = 3

export interface TeamOption { team_id: string; team_name: string; players: number }

/** The teams of the rows of a competition, once each, by name. */
export function teamsOf(rows: SearchRow[]): TeamOption[] {
  const teams = new Map<string, TeamOption>()
  for (const r of rows) {
    const t = teams.get(r.team_id) ?? { team_id: r.team_id, team_name: r.team_name, players: 0 }
    teams.set(r.team_id, { ...t, players: t.players + 1 })
  }
  return [...teams.values()].sort((a, b) => a.team_name.localeCompare(b.team_name) || a.team_id.localeCompare(b.team_id))
}

export interface Squad { rotation: SearchRow[]; bench: SearchRow[] }

export const byMinutes = (a: SearchRow, b: SearchRow) => b.minutes - a.minutes || (a.full_name ?? a.name).localeCompare(b.full_name ?? b.name) || a.person_id.localeCompare(b.person_id)

/** The rows of a team in a competition: the rotation (played enough) by minutes, and the bench. Independent of the order of the rows. */
export function squadOf(rows: SearchRow[], compKey: string, teamId: string): Squad {
  const mine = rows.filter(r => r.comp_key === compKey && r.team_id === teamId).sort(byMinutes)
  return { rotation: mine.filter(r => r.eligible), bench: mine.filter(r => !r.eligible) }
}

export interface GroupBalance { group: PositionGroup; players: number; /** 0 to 1 of the minutes of the rotation with a group */ minutesShare: number }
export interface PositionBalance { groups: GroupBalance[]; unknown: { players: number; minutes: number } }

/** The rotation by position group, with the share of minutes of each: information (the holes are of profile). */
export function positionBalance(rotation: SearchRow[]): PositionBalance {
  const known = rotation.filter(r => r.position_group)
  const unknown = rotation.filter(r => !r.position_group)
  const knownMinutes = known.reduce((s, r) => s + r.minutes, 0)
  const groups = POSITION_GROUPS.map(group => {
    const own = known.filter(r => r.position_group === group)
    return { group, players: own.length, minutesShare: knownMinutes ? own.reduce((s, r) => s + r.minutes, 0) / knownMinutes : 0 }
  })
  return { groups, unknown: { players: unknown.length, minutes: unknown.reduce((s, r) => s + r.minutes, 0) } }
}

export interface AxisCover {
  key: string; label: string; short: string
  /** the best of the rotation in it (null if nobody has the figure) */
  best: SearchRow | null; bestPct: number | null
  /** players of the rotation with the figure */
  players: number; hole: boolean
  /** what the search that would fill it asks for: the metric and how it is called (rebounds: the one of the two where the rotation is weakest) */
  search: { metric: string; label: string }
}

const axisName = (label: string) => label.replace(/ \(.*\)$/, '')

const pctOf = (row: SearchRow, key: string): number | null => (typeof row.pct?.[key as keyof NonNullable<SearchRow['pct']>] === 'number' ? (row.pct![key as keyof NonNullable<SearchRow['pct']>] as number) : null)

/** The axes the rotation is judged on: those of the radar with the two of rebounds as ONE (a player rebounds as the mean of his offensive and defensive percentiles, and needs both). */
export const AXES: { key: string; label: string; short: string; parts: string[] }[] = RADAR_AXES.flatMap(a =>
  a.key === 'drb' ? [] : a.key === 'orb' ? [{ key: 'reb', label: 'Rebotes', short: 'Reb', parts: ['orb', 'drb'] }] : [{ key: a.key, label: axisName(a.label), short: a.short, parts: [a.key] }])

export const valueOf = (row: SearchRow, parts: string[]): number | null => {
  const values = parts.map(k => pctOf(row, k))
  return values.every((v): v is number => v !== null) ? values.reduce((s, v) => s + v, 0) / values.length : null
}

/** For each axis, in the order of the radar: the best player of the rotation and whether nobody covers it (a hole). A tie of the best goes to more minutes, then name and id: independent of the order of the rows. */
export function axisCoverage(rotation: SearchRow[]): AxisCover[] {
  const reliable = rotation.length >= MIN_ROTATION
  return AXES.map(axis => {
    const have = rotation.flatMap(r => { const v = valueOf(r, axis.parts); return v === null ? [] : [{ row: r, v }] })
    const best = [...have].sort((a, b) => b.v - a.v || byMinutes(a.row, b.row))[0]
    // rebounds: ask for the half where the rotation is weakest (the best offensive and the best defensive percentile among the rotation)
    const bestOf = (key: string) => Math.max(-1, ...rotation.map(r => pctOf(r, key) ?? -1))
    const weakest = axis.key === 'reb' ? (bestOf('orb') < bestOf('drb') ? 'orb' : 'drb') : axis.key
    return {
      key: axis.key, label: axis.label, short: axis.short, best: best?.row ?? null, bestPct: best?.v ?? null, players: have.length,
      hole: reliable && have.length >= MIN_WITH_AXIS && best !== undefined && best.v < COVER_PCT,
      search: { metric: weakest, label: axis.key === 'reb' ? (weakest === 'orb' ? 'rebotes ofensivos' : 'rebotes defensivos') : axis.label.toLowerCase() },
    }
  })
}

export interface AgeMix { young: number | null; veteran: number | null; /** share of the minutes of players whose age is not known */ unknown: number }

/** Share of the minutes of the under 22 and the 30 or over among the players with a known age; null when nobody has one. */
export function ageMix(rotation: SearchRow[]): AgeMix {
  const total = rotation.reduce((s, r) => s + r.minutes, 0)
  const withAge = rotation.filter(r => r.age !== null)
  const known = withAge.reduce((s, r) => s + r.minutes, 0)
  const share = (f: (age: number) => boolean) => (known ? withAge.filter(r => f(r.age as number)).reduce((s, r) => s + r.minutes, 0) / known : null)
  return { young: share(a => a < AGE_YOUNG), veteran: share(a => a >= AGE_VETERAN), unknown: total ? (total - known) / total : 0 }
}

export interface Suggestion { key: string; label: string; href: string }

const search = (season: string, patch: Partial<SearchFilters>): string => {
  const params = filtersToParams({ ...NO_FILTERS, onlyEligible: true, ...patch })
  params.set('s', season)
  return `/?${params.toString()}`
}

/** The searches that would fill each hole, already filled in: a percentile of ``SUGGEST_PCT`` or more in the axis nobody covers, the biggest hole (the best player furthest from the percentile) first. */
export function suggestions({ season, coverage }: { season: string; coverage: AxisCover[] }): Suggestion[] {
  return coverage.filter(c => c.hole).sort((a, b) => (a.bestPct as number) - (b.bestPct as number) || a.key.localeCompare(b.key))
    .map(c => ({ key: `axis-${c.key}`, label: `Buscar jugadores de ${c.search.label} (percentil ${SUGGEST_PCT} o más)`, href: search(season, { metric: c.search.metric as SearchFilters['metric'], pctMin: SUGGEST_PCT }) }))
}
