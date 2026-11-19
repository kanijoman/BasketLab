// The shots by zone of a row of Talent (#994), as plain functions over the file of the competition (no React, no network).
//
// Rules: the ten zones of the engine in a fixed order (the same keys and names as the shot chart); a row is a player AND team of a competition (`<person_id>|<team_id>`); the percentage of a zone
// without attempts is NO DATA (null), never a 0 %; the league percentage is the one of ALL the shots of the competition in that zone, so a zone is compared with the same court the player played in.
import type { ShotZoneData } from '@/api/client'
import type { TalentZones } from './data'

export const ZONES = [
  { key: 'restricted_area', label: 'Área restringida', points: 2 }, { key: 'key_area', label: 'Zona', points: 2 }, { key: 'short_mid_range', label: 'Tiro corto', points: 2 },
  { key: 'medium_mid_range', label: 'Tiro medio', points: 2 }, { key: 'long_mid_range', label: 'Tiro largo', points: 2 }, { key: 'left_corner_three', label: 'Esquina izquierda', points: 3 },
  { key: 'left_wing_three', label: '45° izquierda', points: 3 }, { key: 'center_three', label: 'Triple frontal', points: 3 }, { key: 'right_wing_three', label: '45° derecha', points: 3 },
  { key: 'right_corner_three', label: 'Esquina derecha', points: 3 },
] as const
export const ZONE_KEYS = ZONES.map(z => z.key)

export interface ZoneLine { key: string; label: string; points: number; made: number; att: number; pct: number | null; leaguePct: number | null }

const pct = (made: number, att: number): number | null => (att > 0 ? (100 * made) / att : null)

/** The ten zones of a player in a team, or null when the file has no shot of him. */
export function zoneLines(zones: TalentZones, personId: string, teamId: string): ZoneLine[] | null {
  const mine = zones.players[`${personId}|${teamId}`]
  if (!mine) return null
  return zones.zones.map((key, i) => {
    const meta = ZONES.find(z => z.key === key)
    return { key, label: meta?.label ?? key, points: meta?.points ?? 0, made: mine[2 * i], att: mine[2 * i + 1], pct: pct(mine[2 * i], mine[2 * i + 1]), leaguePct: pct(zones.league[2 * i], zones.league[2 * i + 1]) }
  })
}

/** Everything he shot: made and attempted. */
export const zoneTotal = (lines: ZoneLine[]): { made: number; att: number } => ({ made: lines.reduce((a, l) => a + l.made, 0), att: lines.reduce((a, l) => a + l.att, 0) })

/** The points over (or under) the league that make a zone «above» (or «below»): the 8 points of the scouting reports (`scouting_report.zone_excess_pp`). */
export const RATING_PP = 8
/** Fewer attempts than this and the zone is drawn as a small sample (a player has far fewer shots per zone than a team: the 30 of the team reports would leave every zone dashed). */
export const LOW_SAMPLE_ATTEMPTS = 10

/** The zones of a player as the court of Analytics (`FibaCourtSVG`) draws them: a bubble per zone with shots, coloured by how it compares with the league. A zone without shots is left out; one without a
 *  league figure is `unknown`, never invented. The lines are not changed. */
export function zoneChart(lines: ZoneLine[]): ShotZoneData[] {
  return lines.filter(l => l.att > 0).map(l => {
    const delta = l.pct !== null && l.leaguePct !== null ? l.pct - l.leaguePct : null
    return {
      zone: l.key, zone_label: l.label, points: l.points, fga: l.att, fgm: l.made, fg_pct: l.pct ?? 0, league_pct: l.leaguePct, delta_pp: delta,
      rating: delta === null ? 'unknown' : delta >= RATING_PP ? 'above' : delta <= -RATING_PP ? 'below' : 'average', low_sample: l.att < LOW_SAMPLE_ATTEMPTS,
    }
  })
}
