// The profile of a player of BasketLab Talent (epic #872, B4 #880): what the rows of one PERSON say, as plain functions (no React, no network).
//
// A person (`person_id`) has a row per competition, season and team. The profile gathers them: the trajectory (oldest season first, with the main row of each and what changed), the bio
// (each field from his latest row that says it, with where it came from when the roster of that row did not) and the radar of one row's percentiles. Rules that were decided:
//  - a percentile is the player's in HIS competition and season: the radar never mixes competitions, and a field nobody says is NO DATA, never a zero;
//  - the main row of a season is the one with the most minutes (a transfer inside the season keeps both rows); a tie goes to the first by competition and team, so the order of the input
//    does not change the answer;
//  - a person of FBCYL has no bio and, until the identity link is consumed (#979, #980), no row in FEB: the trajectory is what his id has.
import type { SearchRow } from './search'

export const personRows = (all: SearchRow[], personId: string): SearchRow[] => all.filter(r => r.person_id === personId)

export interface SeasonOfPlayer {
  season: string
  season_label: string
  /** The age on 31/12 of the year the season starts in (null when the birth is not known). */
  age: number | null
  /** Every row of the season, the main one first. */
  rows: SearchRow[]
  /** The row with the most minutes. */
  main: SearchRow
  /** What changed since the previous season (by its main row): the competition, or only the team; null for the first season or no change. */
  change: 'competition' | 'team' | null
}

const byMain = (a: SearchRow, b: SearchRow) => b.minutes - a.minutes || a.competition.localeCompare(b.competition) || a.team_id.localeCompare(b.team_id)

/** The seasons of a player, from the oldest, each with its rows and what changed since the previous one. */
export function trajectory(rows: SearchRow[]): SeasonOfPlayer[] {
  const seasons = new Map<string, SearchRow[]>()
  for (const r of rows) seasons.set(r.season, [...(seasons.get(r.season) ?? []), r])
  const out: SeasonOfPlayer[] = []
  for (const season of [...seasons.keys()].sort((a, b) => Number(a) - Number(b) || a.localeCompare(b))) {
    const sorted = [...seasons.get(season)!].sort(byMain)
    const main = sorted[0]
    const before = out[out.length - 1]?.main
    const change = !before ? null : before.competition !== main.competition ? 'competition' : before.team_id !== main.team_id ? 'team' : null
    out.push({ season, season_label: main.season_label, age: main.age, rows: sorted, main, change })
  }
  return out
}

/** A bio field: its value (null when nobody says it) and, when the roster of the row that gave it did not say it, where it came from (`season:team`). */
export interface BioField<T> { value: T | null; from: string | null }

export interface Bio {
  name: string
  birth: BioField<string>
  height: BioField<number>
  position: BioField<string>
  nationality: BioField<string>
}

const latest = (rows: SearchRow[]) => [...rows].sort((a, b) => Number(b.season) - Number(a.season) || a.team_id.localeCompare(b.team_id))

/** The bio of a person: each field from his latest row that says it. */
export function bioOf(rows: SearchRow[]): Bio {
  const ordered = latest(rows)
  const field = <T,>(key: 'birth' | 'height' | 'position' | 'nationality', read: (r: SearchRow) => T | null): BioField<T> => {
    const row = ordered.find(r => read(r) !== null && read(r) !== undefined)
    return row ? { value: read(row), from: row.bio_from?.[key] ?? null } : { value: null, from: null }
  }
  const fine = field('position', r => r.position)
  return {
    name: ordered.find(r => r.full_name)?.full_name ?? ordered[0]?.name ?? '',
    birth: field('birth', r => r.birth),
    height: field('height', r => r.height),
    position: fine.value !== null ? fine : field('position', r => r.position_group),          // the coarse group (G/F/C) only when no row has the fine position
    nationality: field('nationality', r => r.nationality),
  }
}

/** The axes of the radar: the percentiles that describe a player at a glance, in a fixed order. Turnovers are already «more is better» in the percentile. */
export const RADAR_AXES = [
  { key: 'pts', label: 'Puntos' }, { key: 'ast', label: 'Asistencias' }, { key: 'orb', label: 'Reb. ofensivos' }, { key: 'drb', label: 'Reb. defensivos' },
  { key: 'stl', label: 'Robos' }, { key: 'blk', label: 'Tapones' }, { key: 'efg', label: 'Acierto (eFG%)' }, { key: 'tov', label: 'Cuidar el balón (menos pérdidas)' },
] as const

export interface RadarAxis { key: string; label: string; value: number | null }

/** The percentiles of a row on the axes of the radar; null where the row has no profile or no value (never a zero). */
export const radarAxes = (row: SearchRow): RadarAxis[] =>
  RADAR_AXES.map(a => ({ key: a.key, label: a.label, value: row.pct?.[a.key] ?? null }))
