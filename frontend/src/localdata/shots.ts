// Tiros on the device (issue #685): the zone tables, the rating of a zone against the league and the raw shots from the shots a competition publishes (`shots/` of web-data),
// as `src/shotcharts/feb_zones.py` (`aggregate_zones`), `zone_rating.py` (`rate_zone`) and the router of `GET /shots/{collection}[/raw]` answer them. The zone of each shot is
// already in the row (the exporter classified it with the same geometry); what is here is the counting and the rating. Parity: `shots.test.ts` against `tests/local_vectors/shots_*.json`.
import type { ShotRawData, ShotZoneData } from '@/api/client'
import { pyRound } from './pyMath'

/** What the exporter publishes of a competition (`export_shots`): one row per shot, in the order of the competition. */
export interface Shots {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  games: number
  columns: string[]
  /** `[team_id, player_id | null, x, y, made, zone]` */
  shots: [string, string | null, number, number, boolean, string][]
}

export interface ShotFilter { team_id?: string; player?: string }

/** The 10 zones of the FIBA half court, in the order the API lists them (`ZONE_META`). */
const ZONES: [string, string, number][] = [
  ['restricted_area', 'Zona Restringida', 2], ['paint', 'Pintura', 2], ['mid_left', 'Media Izquierda', 2], ['mid_center', 'Media Centro', 2], ['mid_right', 'Media Derecha', 2],
  ['corner_left', 'Triple Esquina Izq', 3], ['wing_left', 'Triple Ala Izq', 3], ['top_three', 'Triple Centro', 3], ['wing_right', 'Triple Ala Der', 3], ['corner_right', 'Triple Esquina Der', 3],
]

/** The shots that pass the team and the player filters (the player is the one of the shot, resolved when the file was made). */
function filtered(shots: Shots, filter: ShotFilter): Shots['shots'] {
  return shots.shots.filter(shot => (filter.team_id === undefined || shot[0] === filter.team_id) && (filter.player === undefined || shot[1] === filter.player))
}

function zoneTable(rows: Shots['shots']): ShotZoneData[] {
  const counts = new Map(ZONES.map(([zone]) => [zone, { fga: 0, fgm: 0 }]))
  for (const [, , , , made, zone] of rows) {
    const count = counts.get(zone)
    if (!count) continue
    count.fga += 1
    if (made) count.fgm += 1
  }
  return ZONES.map(([zone, label, points]) => {
    const { fga, fgm } = counts.get(zone)!
    return { zone, zone_label: label, points, fga, fgm, fg_pct: fga > 0 ? pyRound((fgm / fga) * 100, 1) : 0 }
  })
}

// ── Rating of a zone against the league (`zone_rating.rate_zone`, provisional thresholds) ──────────────────────────────────────────────────────

const Z_THRESHOLD = 1.0
const MIN_DELTA_PP = 2.0
const MIN_FGA = 10
const P_FLOOR = 0.01

const pct = (made: number, attempts: number): number | null => (attempts > 0 ? (made / attempts) * 100 : null)

function rateZone(fgm: number, fga: number, leagueFgm: number, leagueFga: number): Pick<ShotZoneData, 'league_pct' | 'delta_pp' | 'rating' | 'low_sample'> {
  const low = fga < MIN_FGA
  if (fga <= 0) return { league_pct: pct(leagueFgm, leagueFga), delta_pp: null, rating: 'none', low_sample: low }
  if (leagueFga <= 0) return { league_pct: null, delta_pp: null, rating: 'unknown', low_sample: low }
  const p = fgm / fga, pLeague = leagueFgm / leagueFga
  const deltaPp = (p - pLeague) * 100
  const q = Math.min(Math.max(pLeague, P_FLOOR), 1 - P_FLOOR)
  const z = (p - pLeague) / Math.sqrt((q * (1 - q)) / fga)
  let rating: ShotZoneData['rating'] = 'average'
  if (Math.abs(deltaPp) >= MIN_DELTA_PP && Math.abs(z) >= Z_THRESHOLD) rating = deltaPp > 0 ? 'above' : 'below'
  return { league_pct: pLeague * 100, delta_pp: deltaPp, rating, low_sample: low }
}

/** `GET /shots/{collection}`: the 10 zones of the team, the player or the whole competition, and with `compare: 'league'` their rating against the league's same zone. */
export function shotZones(shots: Shots, filter: ShotFilter & { compare?: 'league' }): ShotZoneData[] {
  const zones = zoneTable(filtered(shots, filter))
  if (filter.compare !== 'league') return zones
  const league = filter.team_id !== undefined || filter.player !== undefined ? zoneTable(shots.shots) : zones
  const byZone = new Map(league.map(zone => [zone.zone, zone]))
  return zones.map(zone => ({ ...zone, ...rateZone(zone.fgm, zone.fga, byZone.get(zone.zone)?.fgm ?? 0, byZone.get(zone.zone)?.fga ?? 0) }))
}

/** `GET /shots/{collection}/raw`: the first `limit` shots (5000 by default, 10000 at most) in the order of the competition. */
export function shotRaw(shots: Shots, filter: ShotFilter & { limit?: number }): ShotRawData[] {
  return filtered(shots, filter).slice(0, filter.limit ?? 5000).map(([, , x, y, made, zone]) => ({ x, y, made, zone }))
}
