/** Shot charts: zones and raw shots (issue #201). */
import type { ZoneRating } from '@/lib/zoneRating'
import { fromSource } from '@/datasource/resolve'
import { localShotRaw, localShotZones } from '@/localdata/source'
import { get } from './http'

// ── Shot charts ───────────────────────────────────────────────────────────────

export const getShotZones = (
  collection: string,
  params: { team_id?: string; player?: string; compare?: 'league' },
) => {
  const qs = new URLSearchParams()
  if (params.compare) qs.set('compare', params.compare)
  if (params.team_id) qs.set('team_id', params.team_id)
  if (params.player)  qs.set('player', params.player)
  return fromSource('shots', () => localShotZones(collection, params), () => get<ShotZoneData[]>(`/shots/${encodeURIComponent(collection)}?${qs}`))
}

export const getShotRaw = (
  collection: string,
  params: { team_id?: string; player?: string; limit?: number },
) => {
  const qs = new URLSearchParams()
  if (params.team_id) qs.set('team_id', params.team_id)
  if (params.player)  qs.set('player', params.player)
  if (params.limit)   qs.set('limit', String(params.limit))
  return fromSource('shots', () => localShotRaw(collection, params), () => get<ShotRawData[]>(`/shots/${encodeURIComponent(collection)}/raw?${qs}`))
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
  /** Present with `compare=league`: rating against the quartiles of the competition in this zone (#760). */
  rating?: ZoneRating
  league_pct?: number | null
  delta_pp?: number | null
  /** Weighted position (0-100) of this zone among the competition's teams (players for a player). */
  percentile?: number | null
  /** True when there are too few attempts for the rating to be reliable. */
  low_sample?: boolean
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
