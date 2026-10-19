/** Season figures derived from the play-by-play (#347): points by origin, by period, situations and timeouts (FEB only). */
import { useQuery } from '@tanstack/react-query'

import { API_BASE } from './client'

type Num = number | null

/** `GET /possessions/{collection}/points-by-origin` — own figures and the rival's (`opp_`, what the team concedes). */
export interface OriginRow {
  team_id: string
  team_name: string
  games: number
  games_unreliable: number
  games_paint: number
  pts_off_tov: Num; pts_off_tov_per_game: Num; opp_pts_off_tov: Num; opp_pts_off_tov_per_game: Num
  pts_off_steal: Num; pts_off_steal_per_game: Num; opp_pts_off_steal: Num; opp_pts_off_steal_per_game: Num
  pts_second_chance: Num; pts_second_chance_per_game: Num; opp_pts_second_chance: Num; opp_pts_second_chance_per_game: Num
  pts_bench: Num; pts_bench_per_game: Num; opp_pts_bench: Num; opp_pts_bench_per_game: Num
  pts_paint: Num; pts_paint_per_game: Num; opp_pts_paint: Num; opp_pts_paint_per_game: Num
  oer_off_tov: Num; oer_off_steal: Num; oer_second_chance: Num
  opp_oer_off_tov: Num; opp_oer_off_steal: Num; opp_oer_second_chance: Num
  bench_pct: Num; opp_bench_pct: Num
}

/** One period (`"1"`..`"4"` or `"OT"`) of a team in `GET /possessions/{collection}/by-period`. */
export interface PeriodFigures {
  games: number
  minutes: number
  pts: number; opp_pts: number; pts_per_game: number; opp_pts_per_game: number
  poss: number; opp_poss: number
  ortg: Num; drtg: Num; net_rating: Num; pace: Num
  efg_pct: Num; opp_efg_pct: Num; tov_pct: Num; opp_tov_pct: Num
  orb_pct: Num; drb_pct: Num; ftr: Num; opp_ftr: Num
  fouls_per_game: number; opp_fouls_per_game: number
}

export interface PeriodRow {
  team_id: string
  team_name: string
  games: number
  games_unreliable: number
  periods: Record<string, PeriodFigures>
}

export interface PossessionBlock { n: number; pts: number; ppp: Num }

export interface EdgeFigures {
  pts: number; opp_pts: number; poss: number; opp_poss: number; tov: number; opp_tov: number
  pts_per_game: number; net_rating: Num; tov_pct: Num; opp_tov_pct: Num
  /** Only the first / last two minutes: net rating minus the rest of the period's. */
  vs_rest?: Num
}

/** `GET /possessions/{collection}/situations`. */
export interface SituationRow {
  team_id: string
  team_name: string
  games: number
  games_unreliable: number
  ato_own: PossessionBlock
  ato_rival: PossessionBlock
  first_poss: PossessionBlock
  edges: { start: EdgeFigures; end: EdgeFigures; rest: EdgeFigures }
}

export interface TimeoutGroup {
  n: number
  net_rating_before: Num
  net_rating_after: Num
  delta_net_rating: Num
  pct_caller_improves: Num
}

/** `GET /possessions/{collection}/timeouts`: timeouts the team called (`own`) and the rival called (`rival`). */
export interface TimeoutRow {
  team_id: string
  team_name: string
  own: TimeoutGroup
  rival: TimeoutGroup
}

async function get<T>(collection: string, path: string): Promise<T> {
  const res = await fetch(`${API_BASE}/possessions/${encodeURIComponent(collection)}/${path}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const getPointsByOrigin = (collection: string) => get<OriginRow[]>(collection, 'points-by-origin')
export const getByPeriod = (collection: string) => get<PeriodRow[]>(collection, 'by-period')
export const getSituations = (collection: string) => get<SituationRow[]>(collection, 'situations')
export const getTimeoutEffects = (collection: string) => get<TimeoutRow[]>(collection, 'timeouts')

const STALE = 5 * 60_000

function useRows<T>(key: string, collection: string | undefined, fetcher: (c: string) => Promise<T[]>) {
  return useQuery<T[]>({
    queryKey: ['pbp-extended', key, collection],
    queryFn: () => fetcher(collection!),
    enabled: Boolean(collection),
    staleTime: STALE,
  })
}

export const usePointsByOrigin = (collection?: string) => useRows('origin', collection, getPointsByOrigin)
export const useByPeriod = (collection?: string) => useRows('period', collection, getByPeriod)
export const useSituations = (collection?: string) => useRows('situations', collection, getSituations)
export const useTimeoutEffects = (collection?: string) => useRows('timeouts', collection, getTimeoutEffects)
