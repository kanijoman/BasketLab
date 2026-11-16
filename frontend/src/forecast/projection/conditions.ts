// What a question asks of each scenario of a projection (#936). The possessions and the factors either are or are not what is asked: the scenario is in or out. The points of each side are
// normal around the scenario (the kernel), so a condition on them, or on the points per 100 possessions (the same thing at that scenario's possessions), is an interval of those points. The two
// sides are independent given the scenario, so the probability that it meets the conditions is a product, and the probability that it meets them AND we win is an integral of one variable
// (our points), done with Gauss-Legendre on short pieces split where the integrand bends: exact to far below what is shown, and the same every time.
import { phi } from '../normal'
import type { Projection } from './build'
import { meets, variableOf, type Condition, type Variable } from './variables'

/** An open interval of points; infinite ends when nothing bounds it. */
export interface Interval { lo: number; hi: number }

/** What the conditions ask of one scenario: whether it is in (possessions and factors) and the interval of the points of each side. */
export interface ScenarioQuery { inside: boolean; own: Interval; rival: Interval }

const SPAN = 10                 // kernels either side of the points where the integral is cut (the rest is below 1e-23)
const NODES = 16                // Gauss-Legendre nodes per piece of one kernel of width

const pdf = (t: number): number => Math.exp(-0.5 * t * t) / Math.sqrt(2 * Math.PI)
const cdf = (x: number, m: number, s: number): number => (x === Infinity ? 1 : x === -Infinity ? 0 : phi((x - m) / s))

/** The share of a normal (mean `m`, spread `s`) inside an interval. */
export const share = (iv: Interval, m: number, s: number): number => Math.max(0, cdf(iv.hi, m, s) - cdf(iv.lo, m, s))

/** The mean of a normal (mean `m`, spread `s`) inside an interval; its edge when the interval holds nothing of it. */
export function truncatedMean(iv: Interval, m: number, s: number): number {
  const z = share(iv, m, s)
  if (!(z > 1e-300)) return Number.isFinite(iv.lo) ? iv.lo : Number.isFinite(iv.hi) ? iv.hi : m
  const dens = (x: number): number => (Number.isFinite(x) ? pdf((x - m) / s) : 0)
  return m + (s * (dens(iv.lo) - dens(iv.hi))) / z
}

/** The Gauss-Legendre nodes and weights on [-1, 1] (Newton on the Legendre polynomial, as in Numerical Recipes' `gauleg`). */
function gaussLegendre(n: number): { x: number[]; w: number[] } {
  const x: number[] = []
  const w: number[] = []
  for (let i = 1; i <= n; i++) {
    let z = Math.cos((Math.PI * (i - 0.25)) / (n + 0.5))
    let dp = 0
    for (let it = 0; it < 100; it++) {
      let [p1, p2] = [1, 0]
      for (let j = 1; j <= n; j++) [p1, p2] = [((2 * j - 1) * z * p1 - (j - 1) * p2) / j, p1]
      dp = (n * (z * p1 - p2)) / (z * z - 1)
      const previous = z
      z = previous - p1 / dp
      if (Math.abs(z - previous) < 1e-15) break
    }
    x.push(z)
    w.push(2 / ((1 - z * z) * dp * dp))
  }
  return { x, w }
}

const GL = gaussLegendre(NODES)

/** The integral of `f` from `lo` to `hi` in pieces no wider than `width`. */
function integrate(f: (x: number) => number, lo: number, hi: number, width: number): number {
  const pieces = Math.max(1, Math.ceil((hi - lo) / width))
  const h = (hi - lo) / pieces
  let total = 0
  for (let p = 0; p < pieces; p++) {
    const mid = lo + (p + 0.5) * h
    for (let j = 0; j < NODES; j++) total += GL.w[j] * f(mid + (GL.x[j] * h) / 2)
  }
  return (total * h) / 2
}

/** What a scenario says of a variable that the scenario is (the possessions, a factor of one side). */
export function scenarioValue(p: Projection, i: number, v: Variable): number {
  if (v.measure === 'possessions') return p.possessions[i]
  if (v.measure === 'points' || v.measure === 'oer') throw new Error(`${v.id} is not a value of the scenario`)
  return (v.side === 'own' ? p.fOwn : p.fRiv)[i][v.measure]
}

/** The conditions on scenario `i`: «more than 70 points» is 71 or more, so above 70.5; points per 100 possessions are points at that scenario's possessions. */
export function queryOf(p: Projection, i: number, conditions: Condition[]): ScenarioQuery {
  const q: ScenarioQuery = { inside: true, own: { lo: -Infinity, hi: Infinity }, rival: { lo: -Infinity, hi: Infinity } }
  for (const c of conditions) {
    const v = variableOf(c.variable)
    if (v.kind === 'scenario') {
      q.inside &&= meets(scenarioValue(p, i, v), c)
      continue
    }
    const bound = v.measure === 'points' ? c.value + (c.op === 'gt' ? 0.5 : -0.5) : (c.value * p.possessions[i] * p.minutes[i]) / 100
    const side = v.side === 'own' ? q.own : q.rival
    if (c.op === 'gt') side.lo = Math.max(side.lo, bound)
    else side.hi = Math.min(side.hi, bound)
  }
  return q
}

const unbounded = (iv: Interval): boolean => iv.lo === -Infinity && iv.hi === Infinity

/** The probability that scenario `i` meets what is asked, and that it meets it and we win (we score more than they do). */
export function scenarioOdds(p: Projection, i: number, q: ScenarioQuery): { meets: number; wins: number } {
  if (!q.inside) return { meets: 0, wins: 0 }
  const [a, b, k] = [p.ownPoints[i], p.rivalPoints[i], p.kernel]
  if (unbounded(q.own) && unbounded(q.rival)) return { meets: 1, wins: phi((a - b) / (Math.SQRT2 * k)) }
  const odds = share(q.own, a, k) * share(q.rival, b, k)
  // we win when our points x are above theirs: theirs in their interval and below x
  const from = Math.max(Math.max(q.own.lo, q.rival.lo), Math.min(a, q.own.hi) - SPAN * k)
  const to = Math.min(q.own.hi, Math.max(a, from) + SPAN * k)
  if (!(to > from) || odds === 0) return { meets: odds, wins: 0 }
  const f = (x: number): number => (pdf((x - a) / k) / k) * share({ lo: q.rival.lo, hi: Math.min(q.rival.hi, x) }, b, k)
  const bends = [from, ...(q.rival.hi > from && q.rival.hi < to ? [q.rival.hi] : []), to]
  let wins = 0
  for (let j = 0; j + 1 < bends.length; j++) wins += integrate(f, bends[j], bends[j + 1], k)
  return { meets: odds, wins: Math.min(Math.max(wins, 0), odds) }
}
