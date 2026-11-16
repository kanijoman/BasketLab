// The projection of a match (#936): every scenario of the pool, played by THESE two teams, as a whole game. The possessions and the four factors are those of `scenarios.evaluate` (the pace of
// the matchup times the scenario's ratio; what is expected of this matchup plus the game's residual). The points of each side are those possessions times the minutes of the game times what the
// side is expected to make per 100 possessions plus what that game's side made over its own expectation, so a scenario keeps together, as the game gave them, the pace, the factors and the points
// of both sides: asking for «we score more than 70» brings the pace and the shooting of those games with it.
//
// Around each scenario the points of each side are normal (the kernel, the role of `σ_u`: the season's residuals are in-sample and the ratings are not exact), and one shift of the points (half
// to each side) makes the pool give EXACTLY the headline probability. Nothing is drawn at random: every question is integrated scenario by scenario (`conditions.ts`), so the same question
// always gives the same answer (no Monte Carlo in the preview, decision of #841).
import { bisect, phi } from '../normal'
import { expectedOer, type ForecastModel } from '../pool'
import { evaluate, KERNEL_FLOOR, SEARCH } from '../scenarios'
import type { Factors } from '../factors'
import type { Court, Headline } from '../winProb'

export interface Projection {
  model: ForecastModel
  own: string
  rival: string
  headline: Headline
  /** Per scenario: the possessions per 40 minutes and the minutes over 40 of the game. */
  possessions: number[]
  minutes: number[]
  /** Per scenario: the factors each side makes. */
  fOwn: Factors[]
  fRiv: Factors[]
  /** Per scenario: the expected points of each side, after anchoring. */
  ownPoints: number[]
  rivalPoints: number[]
  /** The spread of the points of each side around its scenario. */
  kernel: number
  /** The points added to ours and taken from theirs (in halves) to anchor the pool, and whether a shift within ±60 points does (if not, the pool is not anchored). */
  shift: number
  anchored: boolean
}

const mean = (xs: number[]): number => xs.reduce((a, b) => a + b, 0) / xs.length
const sd = (xs: number[]): number => Math.sqrt(mean(xs.map(x => (x - mean(xs)) ** 2)))

/** The projection of `own` against `rival` on `court` (null when the competition has no scenarios). */
export function buildProjection(model: ForecastModel, own: string, rival: string, court: Court): Projection | null {
  const ev = evaluate(model, own, rival, court)
  if (!ev) return null
  const { pool } = model
  const minutes = pool.map(s => s.minutes)
  const points = (oer: number, residual: (i: number) => number): number[] => ev.pace.map((n, i) => (n * minutes[i] * (oer + residual(i))) / 100)
  const ours = points(expectedOer(model, own, rival), i => pool[i].oOwn)
  const theirs = points(expectedOer(model, rival, own), i => pool[i].oRiv)
  const margin = ours.map((x, i) => x - theirs[i])
  const kernel = Math.sqrt(Math.max(ev.headline.sigma ** 2 - sd(margin) ** 2, KERNEL_FLOOR ** 2) / 2)
  const spread = Math.SQRT2 * kernel
  const gap = (d: number): number => mean(margin.map(m => phi((m + d) / spread))) - ev.headline.p
  const shift = bisect(gap, -SEARCH, SEARCH, 1e-9)
  return {
    model, own, rival, headline: ev.headline, possessions: ev.pace, minutes, fOwn: ev.fOwn, fRiv: ev.fRiv,
    ownPoints: ours.map(x => x + shift / 2), rivalPoints: theirs.map(x => x - shift / 2), kernel, shift, anchored: Math.abs(gap(shift)) < 1e-6,
  }
}
