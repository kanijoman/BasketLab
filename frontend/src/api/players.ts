/** Players: tables, quartiles, IN/OUT and the shared player types (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localPlayerQuartiles, localInOut, localPlayerStats } from '@/localdata/source'
import { get } from './http'
import type { TeamFilters } from './teams'

// ── Players ───────────────────────────────────────────────────────────────────

export const getPlayerStats = (collection: string, params?: TeamFilters) =>
  fromSource(
    'player-stats',
    () => localPlayerStats(collection, params ?? {}),
    () => {
      const qs = new URLSearchParams()
      if (params?.venue)  qs.set('venue', params.venue)
      if (params?.result) qs.set('result', params.result)
      if (params?.from)   qs.set('from_date', params.from)
      if (params?.to)     qs.set('to_date', params.to)
      if (params?.team)   qs.set('team', params.team)
      const query = qs.toString() ? `?${qs}` : ''
      return get<PlayerStat[]>(`/players/${encodeURIComponent(collection)}${query}`)
    },
  )

export const getPlayerQuartiles = (collection: string) =>
  fromSource('player-stats', () => localPlayerQuartiles(collection), () => get<Record<string, Record<string, number>>>(
    `/players/${encodeURIComponent(collection)}/quartiles`,
  ))

// With the dataset `inout` on (`?data=local`, issue #678) the analysis was computed when the competition was published (FEB): there at once; FBCYL and unpublished ones, the API.
export const getInOutAnalysis = (collection: string, playerId: string) =>
  fromSource(
    'inout',
    () => localInOut(collection, playerId),
    () => get<InOutResult>(`/players/${encodeURIComponent(collection)}/inout/${encodeURIComponent(playerId)}`),
  )

export interface PlayerStat {
  // identity
  player_id: string
  /** FBCYL: the stable id of the player (his `player_id` is the actorId of one game); the analyses and the consistency are keyed by it (#711) */
  player_uuid?: string
  player_name: string
  team_name: string
  team_id?: string
  // volume
  games_played: number
  total_minutes: number
  minutes_per_game: number
  // totals (for display in drawer)
  total_pts?: number
  total_p2m?: number
  total_p2a?: number
  total_p3m?: number
  total_p3a?: number
  total_p1m?: number
  total_p1a?: number
  total_assist?: number
  total_ro?: number
  total_rd?: number
  total_rt?: number
  total_st?: number
  total_to?: number
  total_bs?: number
  total_pf?: number
  total_val?: number
  total_pllss?: number
  // per-game
  points_per_game: number
  rebounds_per_game: number
  offensive_rebounds_per_game?: number
  defensive_rebounds_per_game?: number
  assists_per_game: number
  steals_per_game: number
  blocks_per_game: number
  turnovers_per_game: number
  fouls_per_game?: number
  valoracion_per_game?: number
  pllss_per_game?: number
  // shooting percentages (0–100 scale)
  fg1_percentage?: number   // free throw %
  fg2_percentage?: number
  fg3_percentage?: number
  // advanced shooting / efficiency (pipeline-computed)
  efg_percentage?: number
  true_shooting?: number
  free_throw_rate?: number
  three_point_rate?: number
  turnover_rate?: number
  // advanced metrics (service-computed — need team context)
  usage_pct?: number
  orating?: number
  drating?: number
  net_rtg?: number
  ast_pct?: number
  tov_pct_adv?: number
  stl_pct?: number
  blk_pct?: number
  drb_pct?: number
  orb_pct?: number
  pie?: number
  [key: string]: unknown
}

export interface InOutStatBlock {
  points_for: number
  points_against: number
  minutes: number
  net_rating?: number
  offensive_rating?: number
  defensive_rating?: number
  possessions?: number
  possessions_per_40?: number
  efg_percentage?: number
  true_shooting?: number
  fg2_percentage?: number
  fg3_percentage?: number
  ft_percentage?: number
  three_point_rate?: number
  free_throw_rate?: number
  assist_rate?: number
  turnover_rate?: number
  offensive_rebound_rate?: number
  defensive_rebound_rate?: number
  fg2_made?: number
  fg2_attempts?: number
  fg3_made?: number
  fg3_attempts?: number
  ft_made?: number
  ft_attempts?: number
  assists?: number
  steals?: number
  blocks?: number
  turnovers?: number
  fouls?: number
  off_rebounds?: number
  def_rebounds?: number
  [key: string]: unknown
}

export interface InOutResult {
  player_name: string
  player_id: string
  team_name: string
  on: InOutStatBlock
  off: InOutStatBlock
  /** @deprecated use on/off */
  in?: InOutStatBlock
  /** @deprecated use on/off */
  out?: InOutStatBlock
}
export interface GameLogEntry {
  date: string
  net_rating: number
  ortg: number
  drtg: number
  plus_minus: number
  points_for: number
  points_against: number
  efg_pct: number
  tov_pct: number
  orb_pct: number
  ftr: number
  ast: number
  trb: number
  minutes: number
}
