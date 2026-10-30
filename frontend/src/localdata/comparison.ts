// Comparativas on the device (issue #670): the comparisons of `TeamComparisonService` (`src/services/team_comparison_service.py`) computed from the rows of
// the contract. Each group is the team table of `aggregateTeams` with its own filters, so a figure means the same here as in every other table; per team the
// row has both groups and the REAL difference (group 1 minus group 2, in the unit of the figure), for the team and for what its rivals did against it.
// Parity with the API is enforced by `comparison.test.ts` against `tests/local_vectors/comparison_*.json`.
import type { ComparisonKind, ComparisonRow, TeamComparison, TeamStat } from '@/api/client'
import { aggregateTeams, type GameRow, type LocalTeamStat, type TeamTableFilter } from './aggregateTeams'
import { pyRound } from './pyMath'

/** The numeric figures of the tables of the web (basic and advanced), and the games that say how much each group weighs. */
const COMPARED_FIELDS = [
  'total_games', 'games_home', 'games_away',
  'points_per_game', 'points_against_per_game', 'fg2_percentage', 'fg3_percentage', 'ft_percentage',
  'rebounds_per_game', 'offensive_rebounds_per_game', 'defensive_rebounds_per_game', 'assists_per_game', 'steals_per_game', 'turnovers_per_game', 'blocks_per_game',
  'possessions_per_game', 'offensive_rating', 'defensive_rating', 'net_rating', 'efg_percentage', 'true_shooting', 'three_point_rate', 'free_throw_rate',
  'assist_fg_rate', 'assist_rate', 'turnover_rate', 'steal_rate', 'block_rate', 'offensive_rebound_rate', 'defensive_rebound_rate',
] as const satisfies readonly (keyof TeamStat)[]

const LABELS: Record<ComparisonKind, [string, string]> = { venue: ['Local', 'Visitante'], result: ['Ganados', 'Perdidos'], period: ['Tramo', 'Resto de la temporada'] }

type Figures = Partial<Record<(typeof COMPARED_FIELDS)[number], number>>

const isNumber = (value: unknown): value is number => typeof value === 'number'

function figures(row: LocalTeamStat | undefined): Figures | null {
  if (!row) return null
  const out: Figures = {}
  for (const key of COMPARED_FIELDS) if (row[key] !== undefined && row[key] !== null) out[key] = row[key] as number
  return out
}

/** One team: both groups, their games and the difference of every figure the two have. */
function comparisonRow(name: string, a: LocalTeamStat | undefined, b: LocalTeamStat | undefined): ComparisonRow {
  const fa = figures(a), fb = figures(b)
  const diff: Partial<Record<keyof TeamStat, number>> = {}
  for (const key of COMPARED_FIELDS) {
    const x = fa?.[key], y = fb?.[key]
    if (isNumber(x) && isNumber(y)) diff[key] = pyRound(x - y, 4)
  }
  const source = a ?? b
  return { team_id: source?.team_id, team_name: name, games_a: fa?.total_games ?? 0, games_b: fb?.total_games ?? 0, a: fa, b: fb, diff }
}

/** Teams are matched by name, as the service does. */
function comparisonRows(first: LocalTeamStat[], second: LocalTeamStat[]): ComparisonRow[] {
  const byA = new Map(first.map(r => [String(r.team_name), r]))
  const byB = new Map(second.map(r => [String(r.team_name), r]))
  return [...new Set([...byA.keys(), ...byB.keys()])].sort().map(name => comparisonRow(name, byA.get(name), byB.get(name)))
}

/** The two groups of a comparison as the filters of the team tables, or `null` if there is no such comparison (a stretch needs a date). */
function groups(by: ComparisonKind, range?: { from?: string; to?: string }): [TeamTableFilter, TeamTableFilter] | null {
  if (by === 'venue') return [{ venue: 'home' }, { venue: 'away' }]
  if (by === 'result') return [{ result: 'won' }, { result: 'lost' }]
  if (by === 'period' && (range?.from || range?.to)) {
    const stretch = { from: range.from, to: range.to }
    return [stretch, { ...stretch, outsideDates: true }]                       // the rest of the season: before it and after it
  }
  return null
}

/** The comparison of the competition, or `null` when it cannot be answered here (an unknown kind, a stretch with no date): the API says why. */
export function compareTeams(rows: GameRow[], by: ComparisonKind, range?: { from?: string; to?: string }): TeamComparison | null {
  const filters = groups(by, range)
  if (!filters) return null
  const [a, b] = filters.map(filter => aggregateTeams(rows, filter))
  const [labelA, labelB] = LABELS[by]
  return { by, label_a: labelA, label_b: labelB, team: comparisonRows(a.team_stats, b.team_stats), opponent: comparisonRows(a.opponent_stats, b.opponent_stats) }
}
