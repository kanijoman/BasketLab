// The players like him (epic #872, #1010): how close their percentiles on the eight axes of the radar are, as plain functions (no React, no network).
//
// Rules that were decided (20/11/2026):
//  - only the rows of HIS competition and season are compared (`comp_key`): a percentile is the player's in his own competition, so mixing competitions would compare different things;
//  - only players who played enough (`eligible`) are candidates, and the target must be one himself (the percentiles of who played little are indicative, they do not describe a profile);
//  - the distance is the root of the mean square gap between the percentiles on the axes BOTH have: a missing axis is left out, never a zero, and at least `MIN_SHARED_AXES` of the eight must be in common;
//  - the similarity is 100 minus that gap (in points of percentile), 0 to 100: 100 is the same profile, 90 is ten points apart on average;
//  - the position, the height and the age are NOT part of it (the age is shown beside each one so the staff judges it); a player counts once (his best row) and never as himself;
//  - the order does not depend on the order of the rows: ties go to more minutes, then name, team and id.
import { RADAR_AXES } from './player'
import type { SearchRow } from './search'

export const SIMILAR_LIMIT = 5
export const MIN_SHARED_AXES = 6

export interface Similar { row: SearchRow; /** 0 to 100 */ similarity: number; /** the axes the two have in common */ axes: number }
export interface SimilarResult { similar: Similar[]; reason: 'few-minutes' | 'no-profile' | null }

/** The gap and the axes in common between two rows (null when they share fewer than `MIN_SHARED_AXES`). */
function gap(a: SearchRow, b: SearchRow): { rms: number; axes: number } | null {
  const diffs = RADAR_AXES.flatMap(({ key }) => {
    const x = a.pct?.[key]
    const y = b.pct?.[key]
    return typeof x === 'number' && typeof y === 'number' ? [x - y] : []
  })
  return diffs.length >= MIN_SHARED_AXES ? { rms: Math.sqrt(diffs.reduce((s, d) => s + d * d, 0) / diffs.length), axes: diffs.length } : null
}

const order = (a: Similar, b: Similar) =>
  b.similarity - a.similarity || b.row.minutes - a.row.minutes || (a.row.full_name ?? a.row.name).localeCompare(b.row.full_name ?? b.row.name) || a.row.team_id.localeCompare(b.row.team_id) || a.row.person_id.localeCompare(b.row.person_id)

/** The ``limit`` players of the competition of ``target`` that resemble him most, and why there are none when there are none. The rows are not changed. */
export function similarPlayers(rows: SearchRow[], target: SearchRow, limit = SIMILAR_LIMIT): SimilarResult {
  if (!target.pct) return { similar: [], reason: 'no-profile' }
  if (!target.eligible) return { similar: [], reason: 'few-minutes' }
  const best = new Map<string, Similar>()
  for (const row of rows) {
    if (row.comp_key !== target.comp_key || !row.eligible || row.person_id === target.person_id || row.linked_to === target.person_id) continue
    const g = gap(target, row)
    if (!g) continue
    const mine: Similar = { row, similarity: Math.round((100 - g.rms) * 10) / 10, axes: g.axes }
    const have = best.get(row.person_id)
    if (!have || order(mine, have) < 0) best.set(row.person_id, mine)
  }
  return { similar: [...best.values()].sort(order).slice(0, limit), reason: null }
}
