// «Mi equipo» of BasketLab Talent (epic #872, C1 #882): the squad of a team, where it has holes and the search that would fill each one, as plain functions (no React, no network).
//
// Rules that were decided (20/11/2026):
//  - the staff CHOOSES the team (any competition and season published, senior or youth); where it is remembered is the page's business (the address first, then the browser);
//  - the rotation is who played enough (`eligible`: 10 minutes a game, a third of the games of the team, 3 games); the rest is the bench;
//  - a hole of POSITION is a group (bases and guards, wings, centres) with `HOLE_MAX_PLAYERS` or fewer players of rotation, and it is only said when the rotation has `MIN_ROTATION` players or more.
//    A player with only the group counts in it; one with no position at all is apart and could be anywhere, so a group is a hole only if even all of them together would not get it past the limit;
//  - a hole of PROFILE is one of the three axes of the radar where the rotation is weakest: the percentile (in HIS competition) weighted by minutes; an axis needs three players with the figure;
//  - the age is information (share of the minutes of the under 22 and the 30 or over), never a hole;
//  - the suggestion is a search already filled in (`SUGGEST_PCT` percentile in the weak axis, or the position group, with minutes enough): no ranking of its own.
import { RADAR_AXES } from './player'
import { filtersToParams, NO_FILTERS, POSITION_GROUPS, type PositionGroup, type SearchFilters, type SearchRow } from './search'

export const HOLE_MAX_PLAYERS = 1
export const MIN_ROTATION = 5
export const SUGGEST_PCT = 75
export const AGE_YOUNG = 22
export const AGE_VETERAN = 30
const PROFILE_GAPS = 3
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

const byMinutes = (a: SearchRow, b: SearchRow) => b.minutes - a.minutes || (a.full_name ?? a.name).localeCompare(b.full_name ?? b.name) || a.person_id.localeCompare(b.person_id)

/** The rows of a team in a competition: the rotation (played enough) by minutes, and the bench. Independent of the order of the rows. */
export function squadOf(rows: SearchRow[], compKey: string, teamId: string): Squad {
  const mine = rows.filter(r => r.comp_key === compKey && r.team_id === teamId).sort(byMinutes)
  return { rotation: mine.filter(r => r.eligible), bench: mine.filter(r => !r.eligible) }
}

export interface GroupBalance { group: PositionGroup; players: number; /** 0 to 1 of the minutes of the rotation with a group */ minutesShare: number; hole: boolean }
export interface PositionBalance { groups: GroupBalance[]; unknown: { players: number; minutes: number }; reliable: boolean }

/** The rotation by position group, with the share of minutes of each and the holes. */
export function positionBalance(rotation: SearchRow[]): PositionBalance {
  const known = rotation.filter(r => r.position_group)
  const unknown = rotation.filter(r => !r.position_group)
  const knownMinutes = known.reduce((s, r) => s + r.minutes, 0)
  const reliable = rotation.length >= MIN_ROTATION
  const groups = POSITION_GROUPS.map(group => {
    const own = known.filter(r => r.position_group === group)
    return {
      group, players: own.length, minutesShare: knownMinutes ? own.reduce((s, r) => s + r.minutes, 0) / knownMinutes : 0,
      hole: reliable && own.length + unknown.length <= HOLE_MAX_PLAYERS,
    }
  })
  return { groups, unknown: { players: unknown.length, minutes: unknown.reduce((s, r) => s + r.minutes, 0) }, reliable }
}

export interface ProfileGap { key: string; label: string; short: string; /** weighted percentile, 0 to 100 */ mean: number; players: number }

/** The three axes where the rotation is weakest (the lowest first); none for a rotation too small to say it. */
export function profileGaps(rotation: SearchRow[]): ProfileGap[] {
  if (rotation.length < MIN_ROTATION) return []
  const gaps: ProfileGap[] = []
  for (const axis of RADAR_AXES) {
    const have = rotation.flatMap(r => (typeof r.pct?.[axis.key] === 'number' ? [{ v: r.pct![axis.key] as number, w: r.minutes }] : []))
    const weight = have.reduce((s, h) => s + h.w, 0)
    if (have.length < MIN_WITH_AXIS || weight <= 0) continue
    gaps.push({ key: axis.key, label: axis.label.replace(/ \(.*\)$/, ''), short: axis.short, mean: have.reduce((s, h) => s + h.v * h.w, 0) / weight, players: have.length })
  }
  return gaps.sort((a, b) => a.mean - b.mean || a.key.localeCompare(b.key)).slice(0, PROFILE_GAPS)
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

const GROUP_NAME: Record<PositionGroup, string> = { G: 'bases y escoltas', F: 'aleros y ala-pívots', C: 'pívots' }

/** The searches that would fill each hole, already filled in: the position group of a hole of position, a percentile of ``SUGGEST_PCT`` in a weak axis. */
export function suggestions({ season, balance, gaps }: { season: string; balance: PositionBalance; gaps: ProfileGap[] }): Suggestion[] {
  return [
    ...balance.groups.filter(g => g.hole).map(g => ({ key: `pos-${g.group}`, label: `Buscar ${GROUP_NAME[g.group]}`, href: search(season, { groups: [g.group] }) })),
    ...gaps.map(g => ({ key: `axis-${g.key}`, label: `Buscar jugadores de ${g.label.toLowerCase()} (percentil ${SUGGEST_PCT} o más)`, href: search(season, { metric: g.key as SearchFilters['metric'], pctMin: SUGGEST_PCT }) })),
  ]
}
