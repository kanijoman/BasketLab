// Tiros on the device (issue #685): the zone tables, the rating of a zone against the league and the raw shots from the shots a competition publishes (`shots/` of web-data),
// as `src/shotcharts/feb_zones.py` (`aggregate_zones`), `zone_rating.py` (`rate_zone`) and the router of `GET /shots/{collection}[/raw]` answer them. The zone of each shot is
// already in the row (the exporter classified it with the same geometry); what is here is the counting and the rating. Parity: `shots.test.ts` against `tests/local_vectors/shots_*.json`.
import type { ShotRawData, ShotZoneData } from '@/api/client'
import engineZones from '@/lib/engineZones.json'
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
  /** `engine`: the zones of `live_core.zones` (issue #452); absent: the old system of the web (`feb_zones`), for files published before the change. */
  zone_system?: 'engine'
}

export interface ShotFilter { team_id?: string; player?: string }

type ZoneList = [string, string, number][]

/** The 10 zones of the OLD system of the web, in the order the API listed them (`ZONE_META` of `feb_zones`): files without `zone_system`. It goes with the change of the data (issue #452). */
const LEGACY_ZONES: ZoneList = [
  ['restricted_area', 'Zona Restringida', 2], ['paint', 'Pintura', 2], ['mid_left', 'Media Izquierda', 2], ['mid_center', 'Media Centro', 2], ['mid_right', 'Media Derecha', 2],
  ['corner_left', 'Triple Esquina Izq', 3], ['wing_left', 'Triple Ala Izq', 3], ['top_three', 'Triple Centro', 3], ['wing_right', 'Triple Ala Der', 3], ['corner_right', 'Triple Esquina Der', 3],
]

/** The 10 zones of the engine (`live_core.zones`), in its order: the one file of `lib/engineZones.json` says them for the web. */
const ENGINE_ZONES: ZoneList = Object.entries(engineZones).map(([zone, z]) => [zone, z.label, z.points])

/** The zones a file counts in: its system says which. */
const zonesOf = (shots: Shots): ZoneList => (shots.zone_system === 'engine' ? ENGINE_ZONES : LEGACY_ZONES)

/** The shots that pass the team and the player filters (the player is the one of the shot, resolved when the file was made). */
function filtered(shots: Shots, filter: ShotFilter): Shots['shots'] {
  return shots.shots.filter(shot => (filter.team_id === undefined || shot[0] === filter.team_id) && (filter.player === undefined || shot[1] === filter.player))
}

function zoneTable(rows: Shots['shots'], ZONES: ZoneList): ShotZoneData[] {
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

// ── Rating of a zone against the distribution of the competition (`zone_rating.rate_zone` and `zone_distribution.zone_counts_by_owner`, issue #760) ──────────────────────

const MIN_FGA = 10
const LOWER_QUARTILE = 0.25
const UPPER_QUARTILE = 0.75

type Counts = { fga: number; fgm: number }
type Rating = Pick<ShotZoneData, 'league_pct' | 'delta_pp' | 'percentile' | 'rating' | 'low_sample'>

/** The `q` quantile of `[value, weight]` pairs by the inverse of the weighted cdf (`zone_rating.weighted_quantile`). */
function weightedQuantile(pairs: [number, number][], q: number): number | null {
  const ordered = pairs.filter(([, w]) => w > 0).sort((a, b) => a[0] - b[0])
  const total = ordered.reduce((sum, [, w]) => sum + w, 0)
  if (total <= 0) return null
  const target = q * total
  let cumulative = 0
  for (const [value, weight] of ordered) {
    cumulative += weight
    if (cumulative >= target) return value
  }
  return ordered[ordered.length - 1][0]
}

/** `entities` are the `[fgm, fga]` of every team (or player) of the competition in the zone. */
function rateZone(fgm: number, fga: number, entities: [number, number][]): Rating {
  const low = fga < MIN_FGA
  const shooters = entities.filter(([, att]) => att > 0)
  const totalAtt = shooters.reduce((sum, [, att]) => sum + att, 0)
  const leaguePct = totalAtt > 0 ? (shooters.reduce((sum, [made]) => sum + made, 0) / totalAtt) * 100 : null
  if (fga <= 0) return { league_pct: leaguePct, delta_pp: null, percentile: null, rating: 'none', low_sample: low }
  if (totalAtt <= 0) return { league_pct: null, delta_pp: null, percentile: null, rating: 'unknown', low_sample: low }
  const p = fgm / fga
  const pairs = shooters.map(([made, att]): [number, number] => [made / att, att])
  const q1 = weightedQuantile(pairs, LOWER_QUARTILE)!, q3 = weightedQuantile(pairs, UPPER_QUARTILE)!
  const rating: ShotZoneData['rating'] = p > q3 ? 'above' : p < q1 ? 'below' : 'average'
  const below = pairs.reduce((sum, [value, att]) => sum + (value < p ? att : 0), 0)
  const equal = pairs.reduce((sum, [value, att]) => sum + (value === p ? att : 0), 0)
  return { league_pct: leaguePct, delta_pp: (p - leaguePct! / 100) * 100, percentile: ((below + 0.5 * equal) / totalAtt) * 100, rating, low_sample: low }
}

/** The zone counts of every team, or of every player, of the competition; a shot of a player nobody can name counts for his team and for no player. */
function countsByOwner(rows: Shots['shots'], by: 'team' | 'player', ZONES: ZoneList): Map<string, Map<string, Counts>> {
  const owners = new Map<string, Map<string, Counts>>()
  const known = new Set(ZONES.map(([zone]) => zone))
  for (const [teamId, playerId, , , made, zone] of rows) {
    const owner = by === 'team' ? teamId : playerId
    if (!owner || !known.has(zone)) continue
    let table = owners.get(owner)
    if (!table) owners.set(owner, (table = new Map(ZONES.map(([z]) => [z, { fga: 0, fgm: 0 }]))))
    const count = table.get(zone)!
    count.fga += 1
    if (made) count.fgm += 1
  }
  return owners
}

/** `GET /shots/{collection}`: the 10 zones of the team, the player or the whole competition, and with `compare: 'league'` their rating against how the competition's teams (or players, when a player is asked for) shoot there. */
export function shotZones(shots: Shots, filter: ShotFilter & { compare?: 'league' }): ShotZoneData[] {
  const zones = zoneTable(filtered(shots, filter), zonesOf(shots))
  if (filter.compare !== 'league') return zones
  const owners = [...countsByOwner(shots.shots, filter.player !== undefined ? 'player' : 'team', zonesOf(shots)).values()]
  return zones.map(zone => ({
    ...zone,
    ...rateZone(zone.fgm, zone.fga, owners.map((table): [number, number] => [table.get(zone.zone)!.fgm, table.get(zone.zone)!.fga])),
  }))
}

/** `GET /shots/{collection}/raw`: the first `limit` shots (5000 by default, 10000 at most) in the order of the competition. */
export function shotRaw(shots: Shots, filter: ShotFilter & { limit?: number }): ShotRawData[] {
  return filtered(shots, filter).slice(0, filter.limit ?? 5000).map(([, , x, y, made, zone]) => ({ x, y, made, zone }))
}
