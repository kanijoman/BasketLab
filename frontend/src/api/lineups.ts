/** Lineups: the analysis, its stat groups and the SSE stream (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { streamResult } from './sseStream'
import { localLineups } from '@/localdata/source'
import { BASE, get } from './http'
import type { GameLogEntry } from './players'

// ── Lineups ───────────────────────────────────────────────────────────────────

export const LINEUP_STAT_GROUPS: Array<{
  label: string
  options: Array<{ key: string; label: string }>
}> = [
  {
    label: 'General',
    options: [
      { key: 'net_rating',     label: 'Net Rating' },
      { key: 'plus_minus',     label: 'Diferencial (+/-)' },
      { key: 'points_for',     label: 'Puntos a favor' },
      { key: 'points_against', label: 'Puntos en contra' },
      { key: 'ast',            label: 'Asistencias' },
      { key: 'trb',            label: 'Rebotes totales' },
    ],
  },
  {
    label: 'Avanzadas / Four Factors',
    options: [
      { key: 'ortg',    label: 'Rating Ofensivo (ORtg)' },
      { key: 'drtg',    label: 'Rating Defensivo (DRtg)' },
      { key: 'efg_pct', label: 'eFG%' },
      { key: 'tov_pct', label: 'TOV%' },
      { key: 'orb_pct', label: 'ORB%' },
      { key: 'ftr',     label: 'FT Rate (FTr)' },
    ],
  },
]

/** Period value that means "only the team's most recent game" (sent as `last_game=true`). */
export const LAST_GAME = -1

export const LINEUP_PERIODS: Array<{ value: number; label: string }> = [
  { value: 0,         label: 'Temporada completa' },
  { value: LAST_GAME, label: 'Último partido' },
  { value: 7,         label: 'Últimos 7 días' },
  { value: 15,        label: 'Últimos 15 días' },
  { value: 30,        label: 'Últimos 30 días' },
  { value: 60,        label: 'Últimos 60 días' },
]

function lineupQuery(
  teamName: string, size: number, stat: string, period: number,
  includeGameLog: boolean, minMinutes: number, minGames: number,
): URLSearchParams {
  const qs = new URLSearchParams({
    team_name: teamName,
    size: String(size),
    stat,
    period: String(period === LAST_GAME ? 0 : period),
    include_game_log: String(includeGameLog),
    min_minutes: String(minMinutes),
    min_games: String(minGames),
  })
  if (period === LAST_GAME) qs.set('last_game', 'true')
  return qs
}

/** The table of a team as the page asks for it, from the publication when the dataset `lineups` is on (issue #686; `null` to use the API). */
const localLineupTable = (
  collection: string, teamId: string, size: number, stat: string, period: number, includeGameLog: boolean, minMinutes: number, minGames: number,
): Promise<LineupRow[] | null> => localLineups(collection, teamId, {
  size, stat, period: period === LAST_GAME ? 0 : period, lastGame: period === LAST_GAME, includeGameLog, minMinutes, minGames,
})

export const getLineupAnalysis = (
  collection: string,
  teamId: string,
  teamName: string,
  size = 5,
  stat = 'net_rating',
  period = 0,
  includeGameLog = false,
  minMinutes = 15,
  minGames = 5,
) => {
  const qs = lineupQuery(teamName, size, stat, period, includeGameLog, minMinutes, minGames)
  return fromSource(
    'lineups',
    () => localLineupTable(collection, teamId, size, stat, period, includeGameLog, minMinutes, minGames),
    () => get<LineupRow[]>(`/lineups/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}?${qs}`),
  )
}

/**
 * Stream lineup analysis via SSE.
 * Calls `onProgress(pct, current, total)` for each progress event,
 * then resolves with the full LineupRow[] once the done event arrives.
 * With the dataset `lineups` on (`?data=local`, issue #686) the table is merged on the device from the counters of the publication: it is there at once, no stream.
 */
export function streamLineupAnalysis(
  collection: string,
  teamId: string,
  teamName: string,
  size = 5,
  stat = 'net_rating',
  period = 0,
  includeGameLog = false,
  minMinutes = 15,
  minGames = 5,
  onProgress?: (pct: number, current: number, total: number) => void,
): Promise<LineupRow[]> {
  return fromSource(
    'lineups',
    async () => {
      const table = await localLineupTable(collection, teamId, size, stat, period, includeGameLog, minMinutes, minGames)
      if (table) onProgress?.(100, 1, 1)
      return table
    },
    () => streamLineupsFromApi(collection, teamId, teamName, size, stat, period, includeGameLog, minMinutes, minGames, onProgress),
  )
}

function streamLineupsFromApi(
  collection: string,
  teamId: string,
  teamName: string,
  size: number,
  stat: string,
  period: number,
  includeGameLog: boolean,
  minMinutes: number,
  minGames: number,
  onProgress?: (pct: number, current: number, total: number) => void,
): Promise<LineupRow[]> {
  const qs = lineupQuery(teamName, size, stat, period, includeGameLog, minMinutes, minGames)
  const url = `${BASE}/lineups/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}/stream?${qs}`

  return streamResult<LineupRow[] | undefined>(url, onProgress).then(r => r ?? [])
}

export interface LineupRow {
  players: string[]
  player_ids?: string[]
  player_photo_urls?: string[]
  minutes: number
  games_played?: number
  avg_minutes_per_game?: number
  plus_minus: number
  points_for: number
  points_against: number
  net_rating: number
  ortg?: number
  drtg?: number
  efg_pct?: number
  tov_pct?: number
  orb_pct?: number
  ftr?: number
  ast?: number
  trb?: number
  game_log?: GameLogEntry[]
  [key: string]: unknown
}
