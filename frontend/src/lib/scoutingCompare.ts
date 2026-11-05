// Our team against the scouted one, stat by stat, on the device (issue #751). It is `live_prep/scouting_compare.compare_teams` of the server: a stat is an advantage of one side when
// it is better in the direction that stat has (more points, fewer turnovers) and the two differ by at least `thresholdPct` of the rival's value; tempo and shot-mix stats depend on
// style and have no advantage. `scoutingCompare.test.ts` checks every case of tests/local_vectors/scouting_compare.json, which Python computes.
import { pyFixed } from '@/localdata/pyMath'
import { STAT_CATALOG, type StatDef } from './statCatalog'

export { STAT_CATALOG }
export type { StatDef }

export type Advantage = 'own' | 'rival' | 'even' | 'neutral'

export interface ComparisonRow {
  key: string
  label: string
  group: string
  own: number
  rival: number
  own_text: string
  rival_text: string
  diff_pct: number
  advantage: Advantage
}

export const DEFAULT_THRESHOLD_PCT = 5.0

type Row = Record<string, unknown>

function numberOf(row: Row, key: string): number | null {
  const value = row[key]
  if (value === null || value === undefined) return null
  const n = Number(value)
  return Number.isNaN(n) ? null : n
}

/** The text of a figure as the report says it: one decimal, a comma, «%» after a space (`pyFixed` rounds ties to the even digit, as Python does). */
function text(stat: StatDef, value: number): string {
  const fixed = pyFixed(value, 1).replace('.', ',')
  return stat.pct ? `${fixed} %` : fixed
}

/** The rows of the stats both teams have, the biggest gaps first and the stats of style last. Without the row of a team there is nothing to compare. */
export function compareTeams(own: Row | null | undefined, rival: Row | null | undefined, thresholdPct = DEFAULT_THRESHOLD_PCT): ComparisonRow[] {
  if (!own || !rival) return []
  const rows: ComparisonRow[] = []
  for (const stat of STAT_CATALOG) {
    const a = numberOf(own, stat.key)
    const b = numberOf(rival, stat.key)
    if (a === null || b === null) continue
    const diff = b ? ((a - b) / Math.abs(b)) * 100 : 0
    let advantage: Advantage
    if (stat.higher_is_better === null) advantage = 'neutral'
    else if (Math.abs(diff) < thresholdPct) advantage = 'even'
    else advantage = (diff > 0) === stat.higher_is_better ? 'own' : 'rival'
    rows.push({ key: stat.key, label: stat.label, group: stat.group, own: a, rival: b, own_text: text(stat, a), rival_text: text(stat, b), diff_pct: diff, advantage })
  }
  return rows.sort((x, y) => Number(x.advantage === 'neutral') - Number(y.advantage === 'neutral') || -Math.abs(x.diff_pct) + Math.abs(y.diff_pct))
}
