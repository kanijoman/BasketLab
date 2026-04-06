/**
 * BasketLab API client — v1
 *
 * All requests target /api/v1/ (versioned for future auth middleware).
 * In development the Vite proxy forwards /api/* → localhost:8000.
 * In production set VITE_API_BASE to the FastAPI server URL.
 */

const BASE = (import.meta.env.VITE_API_BASE ?? '') + '/api/v1'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const b = await res.json().catch(() => ({}))
    throw new Error(b.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ── Collections ──────────────────────────────────────────────────────────────

export const getTeamsInCollection = (collection: string) =>
  get<string[]>(`/collections/?collection=${encodeURIComponent(collection)}`)

export const detectFormat = (collection: string) =>
  get<{ collection: string; is_fbcyl: boolean }>(
    `/collections/format?collection=${encodeURIComponent(collection)}`,
  )

export const resolveCollectionName = (
  competition: string,
  season: string,
  group: string,
) =>
  get<{ collection_name: string }>(
    `/collections/resolve?competition=${encodeURIComponent(competition)}&season=${encodeURIComponent(season)}&group=${encodeURIComponent(group)}`,
  )

// ── Teams ─────────────────────────────────────────────────────────────────────

export interface TeamFilters {
  venue?: 'home' | 'away'
  result?: 'won' | 'lost'
  from?: string
  to?: string
}

function buildTeamQs(params?: TeamFilters): string {
  const qs = new URLSearchParams()
  if (params?.venue)  qs.set('venue', params.venue)
  if (params?.result) qs.set('result', params.result)
  if (params?.from)   qs.set('from_date', params.from)
  if (params?.to)     qs.set('to_date', params.to)
  return qs.toString() ? `?${qs}` : ''
}

export const getTeamStats = (collection: string, params?: TeamFilters) =>
  get<{ team_stats: TeamStat[]; opponent_stats: TeamStat[] }>(
    `/teams/${encodeURIComponent(collection)}${buildTeamQs(params)}`,
  )

export const getTeamQuartiles = (collection: string) =>
  get<Record<string, Record<string, number>>>(
    `/teams/${encodeURIComponent(collection)}/quartiles`,
  )

/** @deprecated Use getTeamQuartiles */
export const getQuartiles = getTeamQuartiles

/** Per-team intra-game consistency: {team_name: {stat_key: {mean, std, cv, n}}} */
export interface CVEntry { mean: number; std: number; cv: number; n: number }
export type CVMap = Record<string, Record<string, CVEntry>>
/** Response from the team consistency endpoint: own stats + rival (opponent) stats */
export interface TeamConsistencyResponse { own: CVMap; rival: CVMap }

export const getTeamConsistency = (collection: string) =>
  get<TeamConsistencyResponse>(
    `/teams/${encodeURIComponent(collection)}/consistency`,
  )

/** Per-player intra-game consistency: {player_id: {stat_key: CVEntry}} */
export type ConsistencyMap = CVMap   // alias kept for player stats page
export const getPlayerConsistency = (collection: string) =>
  get<ConsistencyMap>(
    `/players/${encodeURIComponent(collection)}/consistency`,
  )

export const getTeamEvolution = (
  collection: string,
  teamName: string,
  stat: string,
  window = 5,
) =>
  get<EvolutionPoint[]>(
    `/teams/${encodeURIComponent(collection)}/evolution/${encodeURIComponent(teamName)}?stat=${encodeURIComponent(stat)}&window=${window}`,
  )

export const getCompetitionEvolution = (
  collection: string,
  stat: string,
  window = 5,
) =>
  get<CompetitionEvolutionPoint[]>(
    `/teams/${encodeURIComponent(collection)}/competition-evolution?stat=${encodeURIComponent(stat)}&window=${window}`,
  )

// ── Players ───────────────────────────────────────────────────────────────────

export const getPlayerStats = (collection: string, params?: TeamFilters) => {
  const qs = new URLSearchParams()
  if (params?.venue)  qs.set('venue', params.venue)
  if (params?.result) qs.set('result', params.result)
  if (params?.from)   qs.set('from_date', params.from)
  if (params?.to)     qs.set('to_date', params.to)
  const query = qs.toString() ? `?${qs}` : ''
  return get<PlayerStat[]>(`/players/${encodeURIComponent(collection)}${query}`)
}

export const getPlayerQuartiles = (collection: string) =>
  get<Record<string, Record<string, number>>>(
    `/players/${encodeURIComponent(collection)}/quartiles`,
  )

export const getPlayerRankings = (collection: string, stat: string, minMinutes = 0) =>
  get<PlayerStat[]>(
    `/players/${encodeURIComponent(collection)}/rankings?stat=${encodeURIComponent(stat)}&min_minutes=${minMinutes}`,
  )

export const getPlayerRadar = (collection: string, playerId: string) =>
  get<RadarData>(`/players/${encodeURIComponent(collection)}/radar/${encodeURIComponent(playerId)}`)

export const getInOutAnalysis = (collection: string, playerId: string) =>
  get<InOutResult>(
    `/players/${encodeURIComponent(collection)}/inout/${encodeURIComponent(playerId)}`,
  )

export const getPlayersTogether = (collection: string, p1: string, p2: string) =>
  get<PlayersTogetherResult>(
    `/players/${encodeURIComponent(collection)}/together/${encodeURIComponent(p1)}/${encodeURIComponent(p2)}`,
  )

// ── Lineups ───────────────────────────────────────────────────────────────────

export const getLineupAnalysis = (
  collection: string,
  teamId: string,
  teamName: string,
  size = 5,
) =>
  get<LineupRow[]>(
    `/lineups/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}?team_name=${encodeURIComponent(teamName)}&size=${size}`,
  )

// ── Shot charts ───────────────────────────────────────────────────────────────

export const getShotZones = (
  collection: string,
  params: { team?: string; player?: string },
) => {
  const qs = new URLSearchParams()
  if (params.team)   qs.set('team', params.team)
  if (params.player) qs.set('player', params.player)
  return get<ShotZoneData[]>(`/shots/${encodeURIComponent(collection)}?${qs}`)
}

export const getShotRaw = (
  collection: string,
  params: { team?: string; player?: string; limit?: number },
) => {
  const qs = new URLSearchParams()
  if (params.team)   qs.set('team', params.team)
  if (params.player) qs.set('player', params.player)
  if (params.limit)  qs.set('limit', String(params.limit))
  return get<ShotRawData[]>(`/shots/${encodeURIComponent(collection)}/raw?${qs}`)
}

// ── Possessions ───────────────────────────────────────────────────────────────

export const getPossessionStats = (collection: string, params?: TeamFilters) =>
  get<PossessionStat[]>(
    `/possessions/${encodeURIComponent(collection)}${buildTeamQs(params)}`,
  )

// ── AI Analysis ───────────────────────────────────────────────────────────────

export interface AIAnalysisRequest {
  collection: string
  team: string
  analysis_type: 'own' | 'scouting' | 'individual'
  opponent_team?: string
  provider: 'gemini' | 'openai' | 'groq'
  model?: string
  include_shot_chart?: boolean
  include_recommendations?: boolean
}

export const postAIAnalysis = (req: AIAnalysisRequest) =>
  post<{ content: string; output_format: 'pdf' | 'docx' }>('/ai/analyze', req)

export const getAIAnalysisStreamUrl = (req: AIAnalysisRequest): string =>
  `${BASE}/ai/analyze/stream?${new URLSearchParams(req as unknown as Record<string, string>)}`

/** Download the individual scouting DOCX for an entire team. */
export const downloadIndividualScoutingDocx = async (
  collection: string,
  team: string,
  includeAiNotes = true,
): Promise<Blob> => {
  const params = new URLSearchParams({
    collection,
    team,
    include_ai_notes: String(includeAiNotes),
  })
  const res = await fetch(`${BASE}/ai/individual-scouting/docx?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Error descargando DOCX')
  }
  return res.blob()
}

/** Convert streamed AI HTML to PDF and download it. */
export const exportAIAnalysisPDF = async (
  html: string,
  team: string,
  analysisType: string,
): Promise<Blob> => {
  const res = await fetch(`${BASE}/ai/export-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, team, analysis_type: analysisType }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Error generando PDF')
  }
  return res.blob()
}

// ── Shared types ─────────────────────────────────────────────────────────────

export interface TeamStat {
  // identity
  _id?: string
  team_name: string
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

export interface PlayerStat {
  // identity
  player_id: string
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

export interface PlayersTogetherResult {
  together: InOutStatBlock
  apart: InOutStatBlock
}

export interface LineupRow {
  players: string[]
  minutes: number
  plus_minus: number
  points_for: number
  points_against: number
  net_rating: number
  [key: string]: unknown
}

export interface EvolutionPoint {
  game_date: string
  game_number: number
  value: number
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

export interface ShotZoneData {
  zone: string
  zone_label: string
  /** 2 for two-point zone, 3 for three-point zone */
  points: number
  fga: number
  fgm: number
  fg_pct: number
  polygon?: [number, number][]
}

/** Individual shot coordinate for scatter/heatmap modes. */
export interface ShotRawData {
  x: number       // FIBA metres [0-15]
  y: number       // FIBA metres [0-14]
  made: boolean
  zone: string
}

export interface RadarData {
  player_name: string
  axes: { label: string; value: number; league_avg: number }[]
}

export interface PossessionStat {
  team_name: string
  team_id?: string
  possessions_per_game: number
  points_per_100: number
  oer: number
  der: number
  pace: number
  net_rating: number
  total_games: number
  avg_duration: number | null
  pct_fast: number | null
  pct_medium: number | null
  pct_slow: number | null
  oer_fast: number | null
  oer_medium: number | null
  oer_slow: number | null
  est_possessions_per_game: number | null
  [key: string]: unknown
}

// ── Collections management ────────────────────────────────────────────────────

export interface CollectionInfo {
  name: string
  league: 'FEB' | 'FBCYL'
  competition: string
  season: string
  group: string
  game_count: number
}

export const getCollectionList = () =>
  get<CollectionInfo[]>('/collections/list')

export const deleteCollection = (name: string) =>
  fetch(`${BASE}/collections/${encodeURIComponent(name)}`, { method: 'DELETE' })
    .then(res => {
      if (!res.ok) return res.json().then(b => Promise.reject(new Error(b.detail ?? `HTTP ${res.status}`)))
    })

// ── Scraping discovery ────────────────────────────────────────────────────────

export interface DropdownOption {
  text: string
  value: string
}

export interface FbcylInitData {
  seasons: DropdownOption[]
  genders: DropdownOption[]
  territories: DropdownOption[]
}

export const getFebCompetitions = () =>
  get<{ name: string; results_url: string }[]>('/scrape/feb/competitions')

export const getFebSeasons = (url: string, year = '2025') =>
  get<DropdownOption[]>(`/scrape/feb/seasons?url=${encodeURIComponent(url)}&year=${year}`)

export const getFebGroups = (url: string, season: string, year = '2025') =>
  get<DropdownOption[]>(
    `/scrape/feb/groups?url=${encodeURIComponent(url)}&season=${encodeURIComponent(season)}&year=${year}`,
  )

export const getFbcylInit = () =>
  get<FbcylInitData>('/scrape/fbcyl/init')

export const getFbcylCategories = (season: string, gender = '', territory = '0') =>
  get<DropdownOption[]>(
    `/scrape/fbcyl/categories?season=${encodeURIComponent(season)}&gender=${encodeURIComponent(gender)}&territory=${encodeURIComponent(territory)}`,
  )

export const getFbcylCompetitions = (category: string, gender = '', territory = '0') =>
  get<DropdownOption[]>(
    `/scrape/fbcyl/competitions?category=${encodeURIComponent(category)}&gender=${encodeURIComponent(gender)}&territory=${encodeURIComponent(territory)}`,
  )

// ── Scraping jobs ─────────────────────────────────────────────────────────────

export interface FEBScrapeParams {
  competition_url: string
  season_value: string
  group_value: string
  year?: string
  competition_label: string
  season_label: string
  group_label: string
}

export interface FBCYLScrapeParams {
  competition_id: string
  season: string
  gender?: string
  territory?: string
  category: string
  competition_label: string
}

export interface ScrapeRequest {
  league: 'FEB' | 'FBCYL'
  feb?: FEBScrapeParams
  fbcyl?: FBCYLScrapeParams
}

export interface ScrapeJob {
  status: 'starting' | 'discovering' | 'running' | 'done' | 'error'
  total: number
  done: number
  skipped: number
  errors: string[]
  current_match: string | null
  collection: string | null
}

export const postScrapeStart = (req: ScrapeRequest) =>
  post<{ job_id: string }>('/scrape/start', req)

export const getScrapeProgress = (jobId: string) =>
  get<ScrapeJob>(`/scrape/progress/${encodeURIComponent(jobId)}`)

// ── Reports (binary downloads) ────────────────────────────────────────────────

export const getPlayerScoutingUrl = (collection: string, playerId: string) =>
  `${BASE}/reports/${encodeURIComponent(collection)}/player-scouting/${encodeURIComponent(playerId)}`

export const getTeamScoutingUrl = (collection: string, teamName: string) =>
  `${BASE}/reports/${encodeURIComponent(collection)}/team-scouting/${encodeURIComponent(teamName)}`

export const getSeasonSummaryUrl = (collection: string) =>
  `${BASE}/reports/${encodeURIComponent(collection)}/season-summary`
