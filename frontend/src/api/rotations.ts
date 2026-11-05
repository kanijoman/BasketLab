/** Rotations: the analysis of a team and its SSE stream (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localRotation } from '@/localdata/source'
import { BASE } from './http'

// ── Rotaciones ───────────────────────────────────────────────────────────────

export interface RotationPlayer {
  player_id: string
  player_name: string
  total_minutes: number
  games_played: number
  avg_min_per_game: number
  pct_game_time: number
  is_starter: boolean
  starter_games: number
  starter_pct: number
  avg_stint_min: number | null
  total_pbp_stints: number
  is_marginal: boolean
}

export interface RotationResult {
  total_games: number
  games_with_playbyplay: number
  players: RotationPlayer[]
  marginal_players: RotationPlayer[]
  significant_player_count: number
  starting_five_ids: string[]
  starting_five_names: string[]
  starting_five_games_count: number
  starting_five_games_pct: number
  pct_minutes_starting_five: number
  pct_minutes_top5: number
  pct_minutes_top5_std: number
  pct_minutes_top8: number
  pct_minutes_top8_std: number
  total_combined_substitutions: number
  total_individual_substitutions: number
  avg_combined_subs_per_game: number
  avg_individual_subs_per_game: number
  gini_index: number
  gini_std: number
  cv: number
  cv_std: number
  rotation_label: string
  cv_label: string
  avg_stint_min_team: number | null
}

/**
 * Stream rotation analysis via SSE.
 * Calls `onProgress(pct, current, total)` for each progress event,
 * then resolves with the full RotationResult once done.
 */
export function streamRotacionesAnalysis(
  collection: string,
  teamId: string,
  teamName: string,
  onProgress?: (pct: number, current: number, total: number) => void,
): Promise<RotationResult> {
  // With the dataset `rotations` on (`?data=local`, issue #684) the analysis was computed when the competition was published: it is there at once, no stream.
  return fromSource(
    'rotations',
    async () => {
      const published = await localRotation(collection, teamId)
      if (published) onProgress?.(100, 1, 1)
      return published
    },
    () => streamRotationsFromApi(collection, teamId, teamName, onProgress),
  )
}

function streamRotationsFromApi(
  collection: string,
  teamId: string,
  teamName: string,
  onProgress?: (pct: number, current: number, total: number) => void,
): Promise<RotationResult> {
  const qs = new URLSearchParams({ team_name: teamName })
  const url = `${BASE}/rotaciones/${encodeURIComponent(collection)}/${encodeURIComponent(teamId)}/stream?${qs}`

  return new Promise((resolve, reject) => {
    const es = new EventSource(url)

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.done) {
          es.close()
          if (data.error) {
            reject(new Error(data.error))
          } else {
            resolve(data.result as RotationResult)
          }
        } else if (data.progress !== undefined && onProgress) {
          onProgress(data.progress as number, data.current as number, data.total as number)
        }
      } catch {
        // ignore malformed frames
      }
    }

    es.onerror = () => {
      es.close()
      reject(new Error('SSE connection error'))
    }
  })
}
