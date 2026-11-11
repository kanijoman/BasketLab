// The scenarios of a matchup (#847): the pool of the season evaluated for ONE own team against ONE rival, anchored to the win probability of the headline.
//
// Scenario i of the pool says how a real game went against what was expected of its teams. Played by these two teams it becomes: the factors each side makes (what is expected of THIS
// matchup plus what the game's residual was), the possessions (the pace of the matchup times the game's pace ratio) and the expected margin of the game (the expected margin of the matchup
// scaled to those possessions, plus the game's margin residual per root possession). A normal kernel `sigmaU` stands for what the season's residuals do not have (the ratings are not
// exact and the residuals are in-sample), and one bisection on the expected margin makes the pool give EXACTLY the headline probability: the page shows a single number.
import { bisect, phi } from './normal'
import { matchupPace } from './gameLog'
import { expectedFactors, type ForecastModel } from './pool'
import { FACTOR_KEYS, type FactorKey, type Factors } from './factors'
import { headline, type Court, type Headline } from './winProb'

export interface Evaluation {
  own: string
  rival: string
  headline: Headline
  /** What each side is expected to make against the other. */
  expectedOwn: Factors
  expectedRival: Factors
  /** The factors each side makes and the possessions of the game, per scenario. */
  fOwn: Factors[]
  fRiv: Factors[]
  pace: number[]
  /** The expected margin of each scenario after anchoring, in points. */
  mean: number[]
  /** The spread of one scenario around its expected margin (the kernel), and the spread between scenarios before it. */
  sigmaU: number
  residualSd: number
  /** The expected margin of the matchup that makes the pool give the headline probability. */
  muStar: number
  /** False when no expected margin within +-60 points does (the pool is then not anchored). */
  anchored: boolean
}

const KERNEL_FLOOR = 3          // points: the least spread of a scenario around its mean
const SEARCH = 60               // points either side of the headline's expected margin the anchor is looked for in
const mean = (xs: number[]): number => xs.reduce((a, b) => a + b, 0) / xs.length
const sd = (xs: number[]): number => Math.sqrt(mean(xs.map(x => (x - mean(xs)) ** 2)))

/** The matchup of the pool for `own` against `rival` (null when the competition has no scenarios). */
export function evaluate(model: ForecastModel, own: string, rival: string, court: Court): Evaluation | null {
  const { pool } = model
  if (!pool.length) return null
  const head = headline({ ratings: model.ratings, own, rival, court, pace: matchupPace(model.games, own, rival), gender: model.gender })
  const [expectedOwn, expectedRival] = [expectedFactors(model.level(own), model.level(rival), model.league), expectedFactors(model.level(rival), model.level(own), model.league)]
  const pace = pool.map(s => head.pace * s.rho)
  const base = (mu: number): number[] => pool.map((s, i) => mu * s.rho + s.z * Math.sqrt(pace[i]))
  const residualSd = sd(base(head.mu))
  const sigmaU = Math.sqrt(Math.max(head.sigma ** 2 - residualSd ** 2, KERNEL_FLOOR ** 2))
  const gap = (mu: number): number => mean(base(mu).map(m => phi(m / sigmaU))) - head.p
  const muStar = bisect(gap, head.mu - SEARCH, head.mu + SEARCH, 1e-9)
  return {
    own, rival, headline: head, expectedOwn, expectedRival, pace, mean: base(muStar), sigmaU, residualSd, muStar, anchored: Math.abs(gap(muStar)) < 1e-6,
    fOwn: pool.map(s => clamped(expectedOwn, s.dOwn)), fRiv: pool.map(s => clamped(expectedRival, s.dRiv)),
  }
}

const clamped = (expected: Factors, delta: Factors): Factors =>
  Object.fromEntries(FACTOR_KEYS.map(k => [k, Math.min(1, Math.max(0, expected[k] + delta[k]))])) as Factors

export type BucketId = 'lossBig' | 'lossClose' | 'winClose' | 'winBig'

export interface Highlight {
  side: 'own' | 'rival'
  factor: FactorKey
  /** The factor in this kind of game, what was expected, and how many spreads of the factor apart they are. */
  value: number
  expected: number
  z: number
}

export interface Bucket {
  id: BucketId
  /** The margin range, from (excluded) to (included); infinite at the ends. */
  from: number
  to: number
  p: number
  /** The factors of each side and the possessions of a game of this kind. */
  profile: { own: Factors; rival: Factors; pace: number }
  /** The two things (a factor of one side) that set this kind of game apart from what was expected, the most first. */
  highlights: Highlight[]
}

const EDGES: [BucketId, number, number][] = [['lossBig', -Infinity, -10.5], ['lossClose', -10.5, 0], ['winClose', 0, 10.5], ['winBig', 10.5, Infinity]]
const cdf = (x: number, m: number, s: number): number => (x === Infinity ? 1 : x === -Infinity ? 0 : phi((x - m) / s))

function profileOf(weights: number[], ev: Evaluation): Bucket['profile'] {
  const total = weights.reduce((a, b) => a + b, 0)
  const avg = (values: number[]): number => values.reduce((s, v, i) => s + v * weights[i], 0) / total
  const side = (f: Factors[]): Factors => Object.fromEntries(FACTOR_KEYS.map(k => [k, avg(f.map(x => x[k]))])) as Factors
  return { own: side(ev.fOwn), rival: side(ev.fRiv), pace: avg(ev.pace) }
}

function highlightsOf(profile: Bucket['profile'], ev: Evaluation): Highlight[] {
  const rows = (['own', 'rival'] as const).flatMap(side => FACTOR_KEYS.map((factor): Highlight => {
    const spread = sd((side === 'own' ? ev.fOwn : ev.fRiv).map(f => f[factor])) || 1
    const [value, expected] = [profile[side][factor], (side === 'own' ? ev.expectedOwn : ev.expectedRival)[factor]]
    return { side, factor, value, expected, z: (value - expected) / spread }
  }))
  return rows.sort((a, b) => Math.abs(b.z) - Math.abs(a.z)).slice(0, 2)
}

/** The four kinds of game by margin (a big loss, a close one, a close win, a big one) with their probability and what they look like. */
export function bucketsOf(ev: Evaluation): Bucket[] {
  return EDGES.map(([id, from, to]) => {
    const weights = ev.mean.map(m => cdf(to, m, ev.sigmaU) - cdf(from, m, ev.sigmaU))
    const profile = profileOf(weights, ev)
    return { id, from, to, p: mean(weights), profile, highlights: highlightsOf(profile, ev) }
  })
}

/** The probability of each whole margin from -40 to 40 (for the chart). */
export function density(ev: Evaluation): { margin: number; p: number }[] {
  return Array.from({ length: 81 }, (_, i) => {
    const margin = i - 40
    return { margin, p: mean(ev.mean.map(m => cdf(margin + 0.5, m, ev.sigmaU) - cdf(margin - 0.5, m, ev.sigmaU))) }
  })
}
