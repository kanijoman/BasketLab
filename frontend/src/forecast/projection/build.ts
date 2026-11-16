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
import { FACTOR_KEYS, type Factors } from '../factors'
import type { Court, Headline } from '../winProb'
import { extraSlope, type PaceResponse, type ResponseKey } from './paceResponse'

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

export interface ProjectionOptions {
  /** The layer of each team (#937): every scenario moves by what the pace slopes of these two teams say beyond the league's at its pace. Without it, the league's. */
  paceResponse?: PaceResponse
}

const mean = (xs: number[]): number => xs.reduce((a, b) => a + b, 0) / xs.length
const sd = (xs: number[]): number => Math.sqrt(mean(xs.map(x => (x - mean(xs)) ** 2)))

/** The projection of `own` against `rival` on `court` (null when the competition has no scenarios). */
export function buildProjection(model: ForecastModel, own: string, rival: string, court: Court, { paceResponse }: ProjectionOptions = {}): Projection | null {
  const ev = evaluate(model, own, rival, court)
  if (!ev) return null
  const { pool } = model
  const minutes = pool.map(s => s.minutes)
  /** What the layer of each team adds to what `attack` makes against `defender` in scenario i (nothing without the layer). */
  const lift = (attack: string, defender: string, key: ResponseKey): ((i: number) => number) => {
    if (!paceResponse) return () => 0
    const extra = extraSlope(paceResponse, attack, defender, key)
    return i => extra * (pool[i].rho - 1)
  }
  const moved = (fs: Factors[], attack: string, defender: string): Factors[] => {
    if (!paceResponse) return fs
    const lifts = FACTOR_KEYS.map(k => [k, lift(attack, defender, k)] as const)
    return fs.map((f, i) => Object.fromEntries(lifts.map(([k, up]) => [k, Math.min(1, Math.max(0, f[k] + up(i)))])) as Factors)
  }
  const points = (oer: number, residual: (i: number) => number): number[] => ev.pace.map((n, i) => (n * minutes[i] * (oer + residual(i))) / 100)
  const [upOwn, upRival] = [lift(own, rival, 'oer'), lift(rival, own, 'oer')]
  const ours = points(expectedOer(model, own, rival), i => pool[i].oOwn + upOwn(i))
  const theirs = points(expectedOer(model, rival, own), i => pool[i].oRiv + upRival(i))
  const margin = ours.map((x, i) => x - theirs[i])
  const kernel = Math.sqrt(Math.max(ev.headline.sigma ** 2 - sd(margin) ** 2, KERNEL_FLOOR ** 2) / 2)
  const spread = Math.SQRT2 * kernel
  const gap = (d: number): number => mean(margin.map(m => phi((m + d) / spread))) - ev.headline.p
  const shift = bisect(gap, -SEARCH, SEARCH, 1e-9)
  return {
    model, own, rival, headline: ev.headline, possessions: ev.pace, minutes, fOwn: moved(ev.fOwn, own, rival), fRiv: moved(ev.fRiv, rival, own),
    ownPoints: ours.map(x => x + shift / 2), rivalPoints: theirs.map(x => x - shift / 2), kernel, shift, anchored: Math.abs(gap(shift)) < 1e-6,
  }
}
