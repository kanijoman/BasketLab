/**
 * MetricsForAll API client.
 *
 * All requests are relative to the Vite dev-server proxy (/api → localhost:8000).
 * In production, set VITE_API_BASE to the FastAPI server URL.
 */

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ── Collections ─────────────────────────────────────────────────────────────

export const getTeamsInCollection = (collection: string) =>
  get<string[]>(`/api/collections/?collection=${encodeURIComponent(collection)}`)

export const detectFormat = (collection: string) =>
  get<{ collection: string; is_fbcyl: boolean }>(
    `/api/collections/format?collection=${encodeURIComponent(collection)}`,
  )

export const resolveCollectionName = (
  competition: string,
  season: string,
  group: string,
) =>
  get<{ collection_name: string }>(
    `/api/collections/resolve?competition=${encodeURIComponent(competition)}&season=${encodeURIComponent(season)}&group=${encodeURIComponent(group)}`,
  )

// ── Teams ────────────────────────────────────────────────────────────────────

export const getTeamStats = (
  collection: string,
  params?: { venue?: 'home' | 'away'; result?: 'won' | 'lost' },
) => {
  const qs = new URLSearchParams()
  if (params?.venue) qs.set('venue', params.venue)
  if (params?.result) qs.set('result', params.result)
  const query = qs.toString() ? `?${qs}` : ''
  return get<{ team_stats: TeamStat[]; opponent_stats: TeamStat[] }>(
    `/api/teams/${encodeURIComponent(collection)}${query}`,
  )
}

export const getQuartiles = (collection: string) =>
  get<Record<string, Record<string, number>>>(
    `/api/teams/${encodeURIComponent(collection)}/quartiles`,
  )

// ── Players ──────────────────────────────────────────────────────────────────

export const getPlayerStats = (
  collection: string,
  params?: { venue?: 'home' | 'away'; result?: 'won' | 'lost' },
) => {
  const qs = new URLSearchParams()
  if (params?.venue) qs.set('venue', params.venue)
  if (params?.result) qs.set('result', params.result)
  const query = qs.toString() ? `?${qs}` : ''
  return get<PlayerStat[]>(
    `/api/players/${encodeURIComponent(collection)}${query}`,
  )
}

export const getInOutAnalysis = (collection: string, playerId: string) =>
  get<InOutResult>(
    `/api/players/${encodeURIComponent(collection)}/inout/${encodeURIComponent(playerId)}`,
  )

// ── Lineups ──────────────────────────────────────────────────────────────────

export const getLineupAnalysis = (
  collection: string,
  teamId: string,
  teamName: string,
  size = 5,
) =>
  get<LineupRow[]>(
    `/api/lineups/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}?team_name=${encodeURIComponent(teamName)}&size=${size}`,
  )

// ── Shared types ─────────────────────────────────────────────────────────────

export interface TeamStat {
  team_name: string
  games_played: number
  points_per_game: number
  field_goals_2_pct: number
  field_goals_3_pct: number
  free_throw_pct: number
  rebounds_per_game: number
  assists_per_game: number
  steals_per_game: number
  turnovers_per_game: number
  [key: string]: unknown
}

export interface PlayerStat {
  player_name: string
  team_name: string
  games_played: number
  minutes_per_game: number
  points_per_game: number
  rebounds_per_game: number
  assists_per_game: number
  [key: string]: unknown
}

export interface InOutStatBlock {
  points_for: number
  points_against: number
  minutes: number
  [key: string]: unknown
}

export interface InOutResult {
  in: InOutStatBlock
  out: InOutStatBlock
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
