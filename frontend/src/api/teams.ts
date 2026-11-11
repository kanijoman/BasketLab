/** Teams: tables, comparison, consistency and evolution (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localPlayerConsistency, localRivalAdjusted, localTeamEvolution, localCompetitionEvolution, localTeamConsistency, localTeamComparison, localTeamStats } from '@/localdata/source'
import { get } from './http'

// ── Teams ─────────────────────────────────────────────────────────────────────

export interface TeamFilters {
  venue?: 'home' | 'away'
  result?: 'won' | 'lost'
  from?: string
  to?: string
  team?: string
}

function buildTeamQs(params?: TeamFilters): string {
  const qs = new URLSearchParams()
  if (params?.venue)  qs.set('venue', params.venue)
  if (params?.result) qs.set('result', params.result)
  if (params?.from)   qs.set('from_date', params.from)
  if (params?.to)     qs.set('to_date', params.to)
  return qs.toString() ? `?${qs}` : ''
}

// With the dataset `team-stats` on (`?data=local`, issues #327, #329) the tables are computed from the exported files; if they cannot answer, a clear error (`DataNotAvailable`, #334), never the API.
export const getTeamStats = (collection: string, params?: TeamFilters) =>
  fromSource(
    'team-stats',
    () => localTeamStats(collection, params ?? {}),
    () => get<{ team_stats: TeamStat[]; opponent_stats: TeamStat[] }>(`/teams/${encodeURIComponent(collection)}${buildTeamQs(params)}`),
  )

/** Comparative reports of the teams (issue #607): home vs away, won vs lost, a stretch of dates vs the rest of the season. */
export type ComparisonKind = 'venue' | 'result' | 'period'

export interface ComparisonRow {
  team_id?: number | string | null
  team_name: string
  games_a: number
  games_b: number
  a: Partial<TeamStat> | null
  b: Partial<TeamStat> | null
  /** group A minus group B, in the unit of the figure (points for a percentage); a figure missing in a group has none */
  diff: Partial<Record<keyof TeamStat, number>>
}

export interface TeamComparison {
  by: ComparisonKind
  label_a: string
  label_b: string
  team: ComparisonRow[]
  opponent: ComparisonRow[]
}

export const getTeamComparison = (collection: string, by: ComparisonKind, range?: { from?: string; to?: string }) =>
  fromSource(
    'team-comparison',
    () => localTeamComparison(collection, by, range),
    () => {
      const qs = new URLSearchParams({ by })
      if (range?.from) qs.set('from_date', range.from)
      if (range?.to)   qs.set('to_date', range.to)
      return get<TeamComparison>(`/teams/${encodeURIComponent(collection)}/compare?${qs}`)
    },
  )

/** Per-team intra-game consistency: {team_name: {stat_key: {mean, std, cv, n}}} */
export interface CVEntry { mean: number; std: number; cv: number; n: number }
export type CVMap = Record<string, Record<string, CVEntry>>
/** Response from the team consistency endpoint: own stats + rival (opponent) stats */
export interface TeamConsistencyResponse { own: CVMap; rival: CVMap }

// With the dataset `possessions` on (`?data=local`, issue #679) the consistency comes from the same published file as the possessions table.
export const getTeamConsistency = (collection: string) =>
  fromSource(
    'possessions',
    () => localTeamConsistency(collection),
    () => get<TeamConsistencyResponse>(`/teams/${encodeURIComponent(collection)}/consistency`),
  )

/** Per-player intra-game consistency: {player_id: {stat_key: CVEntry}} */
export type ConsistencyMap = CVMap   // alias kept for player stats page
export const getPlayerConsistency = (collection: string) =>
  fromSource('player-consistency', () => localPlayerConsistency(collection), () => get<ConsistencyMap>(
    `/players/${encodeURIComponent(collection)}/consistency`,
  ))

export const getTeamEvolution = (
  collection: string,
  teamId: string,
  stat: string,
  window = 5,
) =>
  fromSource('evolution', () => localTeamEvolution(collection, teamId, stat, window), () => get<EvolutionPoint[]>(
    `/teams/${encodeURIComponent(collection)}/evolution/${encodeURIComponent(teamId)}?stat=${encodeURIComponent(stat)}&window=${window}`,
  ))

export const getCompetitionEvolution = (
  collection: string,
  stat: string,
  window = 5,
) =>
  fromSource(
    'evolution',
    () => localCompetitionEvolution(collection, stat, window),
    () => get<CompetitionEvolutionPoint[]>(
      `/teams/${encodeURIComponent(collection)}/competition-evolution?stat=${encodeURIComponent(stat)}&window=${window}`,
    ),
  )

export interface TeamStat {
  // identity
  _id?: string
  team_name: string
  team_id?: number | string
  // volume
  total_games: number
  games_home: number
  games_away: number
  // basic per-game
  points_per_game: number
  points_against_per_game: number
  possessions_per_game: number
  // rebounding per game
  rebounds_per_game: number
  offensive_rebounds_per_game?: number
  defensive_rebounds_per_game?: number
  assists_per_game: number
  steals_per_game: number
  turnovers_per_game: number
  blocks_per_game: number
  // shooting percentages (0–100 scale)
  fg2_percentage: number
  fg3_percentage: number
  ft_percentage: number
  // four factors
  efg_percentage?: number
  turnover_rate?: number
  offensive_rebound_rate?: number
  free_throw_rate?: number
  // advanced shooting
  three_point_rate?: number
  true_shooting?: number
  // playmaking
  assist_fg_rate?: number
  assist_rate?: number
  steal_rate?: number
  block_rate?: number
  // rebounding
  defensive_rebound_rate?: number
  // efficiency ratings
  offensive_rating?: number
  defensive_rating?: number
  net_rating?: number
  [key: string]: unknown
}

export interface EvolutionPoint {
  game_date: string
  game_number: number
  value: number | null
  rolling_avg?: number | null
  cumulative_avg?: number | null
  won?: boolean
  opponent?: string
}

export interface CompetitionEvolutionPoint {
  game_number: number
  competition_rolling: number | null
  competition_cumulative: number | null
}

// ── Rival-adjusted stats (what the opponents each team met let them do: `rival_adjusted/` of the publication) ──
export interface RivalAdjEntry {
  raw_avg:  number
  adj_avg:  number | null
  adj:      number | null
  sos:      number | null
  n:        number
}
export type RivalAdjustedResult = Record<string, Record<string, RivalAdjEntry>>

export const getRivalAdjusted = (collection: string) =>
  fromSource('rival-adjusted', () => localRivalAdjusted(collection), () => get<RivalAdjustedResult>(
    `/teams/${encodeURIComponent(collection)}/rival-adjusted`,
  ))
