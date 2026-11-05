/** Historical data and predictive analysis (issue #201). */
import { loadReportTeams } from '@/webdata/client'
import { fromSource } from '@/datasource/resolve'
import { localRivalAdjusted } from '@/localdata/source'
import type { TeamEntry } from './collections'
import { get, post } from './http'

// ── Historical (read by the kept predictive code) ─────────────────────────────

export const getHistoricalSeasons = () =>
  get<string[]>('/historical/seasons')

export interface HistoricalTeamEntry {
  team_id: string
  team_name: string
}

export const getHistoricalTeams = (season?: string) =>
  get<HistoricalTeamEntry[]>(
    season ? `/historical/teams?season=${encodeURIComponent(season)}` : '/historical/teams'
  )

// ── Análisis predictivo (FASE 2-5) ───────────────────────────────────────────

// FASE 2 — Rival-adjusted stats
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

// FASE 3/4 — Elasticity models
export interface ElasticityTrainRequest {
  leagues?: string[]
  competitions?: string[]
}
export interface ElasticityModelMeta {
  model_type: 'A' | 'B'
  stat: string
  league: string
  competition: string
  r2_train: number
  n_samples: number
  n_teams: number
  trained_at: string
  features: string[]
}
export interface PredictionEntry {
  estimate: number
  ci_low:   number
  ci_high:  number
  r2:       number
}
export type ElasticityPrediction = Record<string, { model_a?: PredictionEntry; model_b?: PredictionEntry }>

export const postTrainElasticity = (req: ElasticityTrainRequest) =>
  post<Record<string, unknown>>('/analysis/elasticity/train', req)

export const getElasticityModels = () =>
  get<ElasticityModelMeta[]>('/analysis/elasticity/models')

export const getElasticityPredict = (
  teamId: string,
  season: string,
  isHome?: boolean,
  oppNetRtg?: number,
  league?: string,
  competition?: string,
) => {
  const qs = new URLSearchParams({ season })
  if (isHome !== undefined) qs.set('is_home', String(isHome))
  if (oppNetRtg  !== undefined) qs.set('opp_net_rtg', String(oppNetRtg))
  if (league)      qs.set('leagues', league)
  if (competition) qs.set('competitions', competition)
  return get<ElasticityPrediction>(
    `/analysis/elasticity/predict/${encodeURIComponent(teamId)}?${qs}`,
  )
}

export const getElasticityPredictLive = (
  liveCollection: string,
  liveTeamId: string,
  liveIsFbcyl: boolean,
  isHome?: boolean,
  oppNetRtg?: number,
  league?: string,
  competition?: string,
) => {
  const qs = new URLSearchParams({
    live_collection: liveCollection,
    live_team_id: liveTeamId,
    live_is_fbcyl: String(liveIsFbcyl),
  })
  if (isHome !== undefined) qs.set('is_home', String(isHome))
  if (oppNetRtg  !== undefined) qs.set('opp_net_rtg', String(oppNetRtg))
  if (league)      qs.set('leagues', league)
  if (competition) qs.set('competitions', competition)
  // team_id placeholder — ignored by server in live mode
  return get<ElasticityPrediction>(`/analysis/elasticity/predict/_live?${qs}`)
}

// FASE 5 — Monte Carlo
export interface MonteCarloRequest {
  // Historical mode
  season?: string
  // Live mode (current season)
  live_collection?: string
  live_team_id?: string
  live_is_fbcyl?: boolean
  // Shared
  n_games?: number
  n_simulations?: number
  is_home_schedule?: boolean[]
  opp_net_rtg_schedule?: number[]
  leagues?: string[]
  competitions?: string[]
}

export const getLiveTeamNames = (collection: string) =>
  fromSource('report-teams', () => loadReportTeams(collection), () => get<TeamEntry[]>(`/teams/${encodeURIComponent(collection)}/teams`))
export interface SimulatedGameStat {
  mean:    number
  std:     number
  ci_low:  number
  ci_high: number
}
export interface SimulatedGame {
  game_index:  number
  is_home:     boolean | null
  opp_net_rtg: number | null
  win_prob:    number
  stats: Record<string, SimulatedGameStat>
}
export interface MonteCarloResult {
  team_id:                 string
  season:                  string
  n_games:                 number
  n_simulations:           number
  games:                   SimulatedGame[]
  projected_wins_mean:     number
  projected_wins_std:      number
  projected_wins_ci_low:   number
  projected_wins_ci_high:  number
}

export const postMonteCarlo = (teamId: string, req: MonteCarloRequest) =>
  post<MonteCarloResult>(
    `/analysis/montecarlo/${encodeURIComponent(teamId)}`,
    req,
  )

// ── Backtesting (FASE 6) ─────────────────────────────────────────────────────

export interface BacktestingMetrics {
  mae:          number | null
  rmse:         number | null
  mape:         number | null
  n_evaluated:  number
}

export interface BacktestingNaiveMetrics {
  mae:         number | null
  rmse:        number | null
  n_evaluated: number
}

export interface BacktestingStatResult {
  model_a: BacktestingMetrics
  model_b: BacktestingMetrics
  naive:   BacktestingNaiveMetrics
}

export type BacktestingResult = Record<string, BacktestingStatResult>

export const getBacktesting = (
  teamId:  string,
  season:  string,
  leagues?: string,
  competitions?: string,
) => {
  const params = new URLSearchParams({ season })
  if (leagues)      params.set('leagues', leagues)
  if (competitions) params.set('competitions', competitions)
  return get<BacktestingResult>(
    `/analysis/backtesting/${encodeURIComponent(teamId)}?${params}`,
  )
}

export const getBacktestingLive = (
  collection: string,
  teamId:     string,
  isFbcyl:    boolean,
) => {
  const params = new URLSearchParams({ is_fbcyl: String(isFbcyl) })
  return get<BacktestingResult>(
    `/analysis/backtesting-live/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}?${params}`,
  )
}

// ── Game Prediction (FASE 7) ─────────────────────────────────────────────────

export interface GamePredictionRequest {
  season?:          string
  is_home:          boolean
  opp_net_rtg?:     number
  live_collection?: string
  live_team_id?:    string
  live_is_fbcyl?:   boolean
  leagues?:         string[]
  competitions?:    string[]
}

export interface GamePredictionResult {
  win_prob:              number
  ci_low:                number
  ci_high:               number
  feature_importances:   Record<string, number>
  feature_coefficients:  Record<string, number>
  n_train:               number
  accuracy:              number | null
}

export const postGamePrediction = (teamId: string, req: GamePredictionRequest) =>
  post<GamePredictionResult>(
    `/analysis/game-prediction/${encodeURIComponent(teamId)}`,
    req,
  )

// ── Player Prediction (FASE 8) ───────────────────────────────────────────────

export interface PlayerPredictionStat {
  estimate: number | null
  ci_low:   number | null
  ci_high:  number | null
  n_train:  number
}

export interface PlayerPredictionResult {
  pts: PlayerPredictionStat
  reb: PlayerPredictionStat
  ast: PlayerPredictionStat
  val: PlayerPredictionStat
}

export const getPlayerPrediction = (
  collection: string,
  playerId: string,
  isHome: boolean,
  oppNetRtg: number = 0,
  isFbcyl: boolean = false,
) => {
  const qs = new URLSearchParams({
    is_home:     String(isHome),
    opp_net_rtg: String(oppNetRtg),
    is_fbcyl:    String(isFbcyl),
  })
  return get<PlayerPredictionResult>(
    `/analysis/player-prediction/${encodeURIComponent(collection)}/${encodeURIComponent(playerId)}?${qs}`,
  )
}

// ── Season Projection (FASE 9) ───────────────────────────────────────────────

export interface SeasonProjectionEntry {
  team_id:           string
  team_name:         string
  wins_so_far:       number
  losses_so_far:     number
  proj_wins:         number
  proj_losses:       number
  proj_wins_ci_low:  number
  proj_wins_ci_high: number
  playoff_prob:      number
  rank_probs:        Record<number, number>
}

export const getSeasonProjection = (
  collection: string,
  seasonLength: number = 22,
  nSimulations: number = 1000,
  playoffSpots: number = 4,
  isFbcyl: boolean = false,
) => {
  const qs = new URLSearchParams({
    season_length: String(seasonLength),
    n_simulations: String(nSimulations),
    playoff_spots: String(playoffSpots),
    is_fbcyl:      String(isFbcyl),
  })
  return get<SeasonProjectionEntry[]>(
    `/analysis/season-projection/${encodeURIComponent(collection)}?${qs}`,
  )
}
