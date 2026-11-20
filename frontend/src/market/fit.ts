// The fit of a player with «Mi equipo» (epic #872, C2 #883): what he adds to the holes of the rotation, where he collides with who is already good at it, whom he would replace and the rotation that
// results, as plain functions (no React, no network). It reuses the rules of the squad (`myTeam.ts`) and of the parallels (`similar.ts`); nothing here ranks players.
//
// Rules that were decided (20/11/2026):
//  - the percentiles are each player's in HIS competition (never translated to the one of the team: that is the scoring of #894), so a verdict from another competition is indicative; the page says it;
//  - he STANDS OUT in an axis when he reaches `COVER_PCT`, the same percentile that makes a rotation cover it; rebounds are one axis (the mean of the two percentiles), as in the holes;
//  - he COMPLEMENTS when he stands out in an axis that is a hole of the rotation; he COLLIDES when he stands out only where somebody of the rotation already does (the best of them is named); he is NEUTRAL
//    when he stands out in nothing. A collision is information, not a reason to discard him: whom he would replace says how much;
//  - he REPLACES the player of the rotation whose profile is closest when the similarity reaches `SUBSTITUTE_SIMILARITY` (the rule of the parallels: 100 minus the mean gap of percentiles); if nobody is
//    that close he is added to the rotation. The simulated rotation recomputes the holes: `opens` are the holes that were not and are now (the one he replaces was the only one who covered them);
//  - nothing is said when he has no profile or few minutes, when he is already in the team (or linked to one of its players) or when the rotation is smaller than `MIN_ROTATION`.
import { profileSimilarity } from './similar'
import { AXES, COVER_PCT, MIN_ROTATION, axisCoverage, byMinutes, valueOf, type AxisCover } from './myTeam'
import type { SearchRow } from './search'

export const SUBSTITUTE_SIMILARITY = 85

export type FitReason = 'no-profile' | 'in-team' | 'few-minutes' | 'small-rotation'
export type Verdict = 'complements' | 'collides' | 'neutral'
export interface Collision { axis: AxisCover; /** the best of the rotation in the axis */ by: SearchRow }
export interface Fit {
  reason: FitReason | null
  verdict: Verdict | null
  /** the holes of the rotation where he stands out */
  fills: AxisCover[]
  /** the axes where he stands out and somebody of the rotation already does */
  collides: Collision[]
  substitute: { row: SearchRow; similarity: number } | null
  /** the player he replaces in the simulation (null: he is added) */
  replaced: SearchRow | null
  before: AxisCover[]
  after: AxisCover[]
  /** keys of the axes that are holes before / after, in the order of the radar */
  holesBefore: string[]
  holesAfter: string[]
  /** holes that appear when he takes the place of the one he replaces */
  opens: string[]
}

const EMPTY: Omit<Fit, 'reason'> = { verdict: null, fills: [], collides: [], substitute: null, replaced: null, before: [], after: [], holesBefore: [], holesAfter: [], opens: [] }
const holes = (coverage: AxisCover[]) => coverage.filter(a => a.hole).map(a => a.key)
const inTeam = (rotation: SearchRow[], c: SearchRow) => rotation.some(r => r.person_id === c.person_id || r.person_id === c.linked_to || r.linked_to === c.person_id)

/** Whom the candidate resembles most in the rotation, when close enough. A tie goes to more minutes, then name and id: independent of the order of the rows. */
function closest(rotation: SearchRow[], candidate: SearchRow): { row: SearchRow; similarity: number } | null {
  const ranked = rotation.flatMap(row => { const s = profileSimilarity(candidate, row); return s ? [{ row, similarity: s.similarity }] : [] })
    .sort((a, b) => b.similarity - a.similarity || byMinutes(a.row, b.row))
  return ranked[0] && ranked[0].similarity >= SUBSTITUTE_SIMILARITY ? ranked[0] : null
}

/** The fit of ``candidate`` with ``rotation`` (the rotation of a team, see `squadOf`); the rows are not changed. */
export function fitIn(rotation: SearchRow[], candidate: SearchRow): Fit {
  if (!candidate.pct) return { ...EMPTY, reason: 'no-profile' }
  if (inTeam(rotation, candidate)) return { ...EMPTY, reason: 'in-team' }
  if (!candidate.eligible) return { ...EMPTY, reason: 'few-minutes' }
  if (rotation.length < MIN_ROTATION) return { ...EMPTY, reason: 'small-rotation' }
  const before = axisCoverage(rotation)
  const strong = AXES.filter(axis => (valueOf(candidate, axis.parts) ?? -1) >= COVER_PCT).map(axis => axis.key)
  const fills = before.filter(a => a.hole && strong.includes(a.key))
  const collides = before.filter(a => !a.hole && a.best !== null && (a.bestPct as number) >= COVER_PCT && strong.includes(a.key)).map(axis => ({ axis, by: axis.best as SearchRow }))
  const substitute = closest(rotation, candidate)
  const replaced = substitute?.row ?? null
  const after = axisCoverage([...rotation.filter(r => r !== replaced), candidate])
  const holesBefore = holes(before)
  const holesAfter = holes(after)
  return {
    reason: null, verdict: fills.length ? 'complements' : collides.length ? 'collides' : 'neutral', fills, collides, substitute, replaced, before, after,
    holesBefore, holesAfter, opens: holesAfter.filter(k => !holesBefore.includes(k)),
  }
}
