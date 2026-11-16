// The objectives of the match (#847): what to do in the game, ranked by how much better the matchup goes when it happens.
//
// Per thing a team can do (the four factors it makes, the four it lets the rival make, and the pace) the TARGET is where the 25 % of the scenarios of THIS matchup that go best in that direction
// begin (so every objective has the same weight and they can be ranked against each other, and the target is a game that happens one in four). The objective says how often we win in those
// games against how often we win overall, and how the season went when our own games got there: it is the projection of the match asked for that condition (#941), so the card «¿Y si…?» gives
// the same figure for the same thing. It is CONDITIONAL: «in the games where this happens, we win this often». The study of 26/10/2026 found no evidence that correcting a factor during a game
// changes what follows, so nothing here says that making it happen makes us win. What the walk-forward evaluation does not back is INFORMATION (what is expected and how the season went at
// either end), not an objective: the pace (#857) and our turnovers (16/11/2026, calibrated but no better than the headline: docs/evaluaciones/2026-11-16_proyeccion-multifactorial.md).
import { FACTOR_KEYS, type FactorKey } from './factors'
import type { Evaluation } from './scenarios'
import type { Projection } from './projection/build'
import { scenarioValues } from './projection/conditions'
import { project, seasonRecord } from './projection/project'
import { variableOf, type Condition, type VariableId } from './projection/variables'

export interface Lever {
  side: 'attack' | 'defence' | 'pace'
  /** The factor (none for the pace). */
  factor?: FactorKey
  /** The variable of the projection it is a condition on. */
  variable: VariableId
  /** `up`: the thing must be over the target; `down`: under it. */
  direction: 'up' | 'down'
  threshold: number
  /** What is expected of this thing in this matchup (the pace: the usual possessions). */
  expected: number
  /** The probability of winning in the games past the target, and what it adds to the headline. */
  pWin: number
  gain: number
  /** The share of the games like this one past the target. */
  mass: number
  /** The own team's games of the season past the target and the ones it won. */
  record: { reached: number; won: number }
}

/** The own games under (`low`) or over (`high`) a threshold, and how they went. */
export interface Band { threshold: number; record: { reached: number; won: number } }

/**
 * Something the page tells as INFORMATION and not as an objective, because the walk-forward evaluation does not back a probability of winning when it happens: what is expected of it in this
 * matchup, and how the season went in the own games at the low end (the quarter of the scenarios with the least of it) and at the high end. The pace (#857: for the men the model says 52 % and
 * the games 44 %, for the women 54 % and 63 %) and our turnovers (16/11/2026).
 */
export interface BandInfo { variable: VariableId; expected: number; low: Band; high: Band }

export interface Levers { attack: Lever[]; defence: Lever[]; info: BandInfo[] }

const SHARE = 0.25          // the scenarios that go best, the part that defines a target
const MIN_GAIN = 0.01       // what an objective must add to the probability to be worth listing
const PER_SIDE = 3
/** Is more of the factor good for the team that makes it? (turnovers: no) */
const GOOD_UP: Record<FactorKey, boolean> = { efg: true, tov: false, orb: true, ftr: true }

/** The linear quantile (NumPy's default). */
export function quantile(values: number[], q: number): number {
  const sorted = [...values].sort((a, b) => a - b)
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  return sorted[lo] + (sorted[Math.ceil(pos)] - sorted[lo]) * (pos - lo)
}

/** The condition of the projection an objective is: over the target (`up`) or under it. */
export const leverCondition = (l: Pick<Lever, 'variable' | 'direction' | 'threshold'>): Condition => ({ variable: l.variable, op: l.direction === 'up' ? 'gt' : 'lt', value: l.threshold })

/** One objective for a variable: `sign` is +1 when more of it is better (the target is where its top quarter of the scenarios begins) and -1 when less is (where its bottom quarter ends). */
function leverOf(p: Projection, variable: VariableId, sign: 1 | -1, base: Pick<Lever, 'side' | 'factor' | 'expected'>): Lever {
  const threshold = sign * quantile(scenarioValues(p, variable).map(v => sign * v), 1 - SHARE)
  const direction = sign > 0 ? 'up' : 'down'
  const r = project(p, [leverCondition({ variable, direction, threshold })])
  return { ...base, variable, direction, threshold, pWin: r.pWin, gain: r.pWin - p.headline.p, mass: r.mass, record: counts(r.record) }
}

const counts = ({ reached, won }: Band['record']): Band['record'] => ({ reached, won })

/** The low and the high end of a variable in this matchup, and the own games of the season past each. */
function bandsOf(p: Projection, variable: VariableId, expected: number): BandInfo {
  const values = scenarioValues(p, variable)
  const band = (op: Condition['op'], q: number): Band => {
    const threshold = quantile(values, q)
    return { threshold, record: counts(seasonRecord(p.model, p.own, [{ variable, op, value: threshold }])) }
  }
  return { variable, expected, low: band('lt', SHARE), high: band('gt', 1 - SHARE) }
}

/**
 * The two pace candidates of a matchup (the fast quarter of the scenarios and the slow one) with the probability of winning in each, as an objective would have: NOT shown by the page (see
 * `BandInfo`), kept so that the evaluation can go on measuring whether the pace deserves to be an objective.
 */
export function paceCandidates(p: Projection, ev: Evaluation): Lever[] {
  return [1, -1].map(sign => leverOf(p, 'game.possessions', sign as 1 | -1, { side: 'pace', expected: ev.headline.pace }))
}

/** The pace candidate that would be listed as an objective (the one that adds most, if it adds a point of probability), or none. */
export const bestPaceLever = (candidates: Lever[]): Lever | null => candidates.filter(l => l.gain >= MIN_GAIN).sort((a, b) => b.gain - a.gain)[0] ?? null

/**
 * The objectives of an own team in a matchup (`p`, the projection of the match, and `ev`, its scenarios): up to three of attack and three of defence, each worth at least a point of probability
 * and backed by the evaluation, and the rest as information (the pace, and the factors without that support).
 */
export function leversOf(p: Projection, ev: Evaluation): Levers {
  const candidates = (['attack', 'defence'] as const).flatMap(side => FACTOR_KEYS.map(factor => leverOf(p, `${side === 'attack' ? 'own' : 'rival'}.${factor}`,
    GOOD_UP[factor] === (side === 'attack') ? 1 : -1, { side, factor, expected: (side === 'attack' ? ev.expectedOwn : ev.expectedRival)[factor] })))
  const backed = (l: Lever): boolean => variableOf(l.variable).supported
  const listed = (side: Lever['side']): Lever[] => candidates.filter(l => l.side === side && backed(l) && l.gain >= MIN_GAIN).sort((a, b) => b.gain - a.gain).slice(0, PER_SIDE)
  const info = [bandsOf(p, 'game.possessions', ev.headline.pace), ...candidates.filter(l => !backed(l)).map(l => bandsOf(p, l.variable, l.expected))]
  return { attack: listed('attack'), defence: listed('defence'), info }
}
