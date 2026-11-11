// The objectives of the match (#847): what to do in the game, ranked by how much better the matchup goes when it happens.
//
// Per thing a team can do (the four factors it makes, the four it lets the rival make, and the pace) the TARGET is where the 25 % of the scenarios of THIS matchup that go best in that direction
// begin (so every objective has the same weight and they can be ranked against each other, and the target is a game that happens one in four). The objective says how often we win in those
// scenarios against how often we win overall, and how the season went when our own games got there. It is CONDITIONAL: «in the games where this happens, we win this often». The study of
// 26/10/2026 found no evidence that correcting a factor during a game changes what follows, so nothing here says that making it happen makes us win.
import { FACTOR_KEYS, boxOf, factors, type FactorKey } from './factors'
import { phi } from './normal'
import type { Evaluation } from './scenarios'
import type { ForecastModel } from './pool'
import type { GameResult } from './gameLog'

export interface Lever {
  side: 'attack' | 'defence' | 'pace'
  /** The factor (none for the pace). */
  factor?: FactorKey
  /** `up`: the thing must be at least the target; `down`: at most. */
  direction: 'up' | 'down'
  threshold: number
  /** What is expected of this thing in this matchup (the pace: the usual possessions). */
  expected: number
  /** The probability of winning in the scenarios that reach the target, and what it adds to the headline. */
  pWin: number
  gain: number
  /** The share of the scenarios that reach it. */
  mass: number
  /** The own team's games of the season that reached the target and the ones it won. */
  record: { reached: number; won: number }
}

/** The own games played at a pace that slow or that fast, and how they went. */
export interface PaceBand { threshold: number; record: { reached: number; won: number } }

/**
 * The pace is INFORMATION, not an objective (#857): the walk-forward evaluation of 11/11/2026 (2,561 games of 12 competitions, men and women) found no support for a probability of winning at a
 * given pace: for the men the model says 52 % and the games 44 %, for the women 54 % and 63 %, on a few hundred cases that the standard error leaves in the noise. So the page says what pace is
 * expected and how the season went at a slow and at a fast one, and no more.
 */
export interface PaceInfo { expected: number; slow: PaceBand; fast: PaceBand }

export interface Levers { attack: Lever[]; defence: Lever[]; pace: PaceInfo }

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

/** What the games of `team` that have a box score say of a metric: `value(game side)` for each. */
function ownGames(model: ForecastModel, team: string): { game: GameResult; home: boolean }[] {
  return model.games.filter(g => g.homeRow && (g.home === team || g.away === team)).map(game => ({ game, home: game.home === team }))
}

const wins = ({ game, home }: { game: GameResult; home: boolean }): boolean => (home ? game.margin : -game.margin) > 0

/** One objective for a metric: `sign` is +1 when more of it is better (the target is its 75th percentile) and -1 when less is (its 25th). */
function leverOf(ev: Evaluation, probs: number[], values: number[], sign: 1 | -1, base: Omit<Lever, 'direction' | 'threshold' | 'pWin' | 'gain' | 'mass' | 'record'>, record: (past: (v: number) => boolean) => Lever['record']): Lever {
  const signed = values.map(v => sign * v)
  const cut = quantile(signed, 1 - SHARE)
  const inside = signed.map(v => v >= cut)
  const count = inside.filter(Boolean).length
  const pWin = probs.reduce((s, p, i) => s + (inside[i] ? p : 0), 0) / count
  const threshold = sign * cut
  return { ...base, direction: sign > 0 ? 'up' : 'down', threshold, pWin, gain: pWin - ev.headline.p, mass: count / values.length, record: record(v => sign * v >= cut) }
}

/** What the games and the scenarios say about a team in a matchup, for the objectives and for the pace. */
function context(model: ForecastModel, ev: Evaluation) {
  const probs = ev.mean.map(m => phi(m / ev.sigmaU))
  const mine = ownGames(model, ev.own)
  const recordOf = (value: (g: { game: GameResult; home: boolean }) => number | null) => (past: (v: number) => boolean): Lever['record'] => {
    const reached = mine.filter(g => { const v = value(g); return v !== null && past(v) })
    return { reached: reached.length, won: reached.filter(wins).length }
  }
  return { probs, recordOf }
}

/**
 * The two pace candidates of a matchup (the fast quarter of the scenarios and the slow one) with the probability of winning in each, as an objective would have: NOT shown by the page (see
 * `PaceInfo`), kept so that the evaluation can go on measuring whether the pace deserves to be an objective.
 */
export function paceCandidates(model: ForecastModel, ev: Evaluation): Lever[] {
  const { probs, recordOf } = context(model, ev)
  const base = { side: 'pace' as const, expected: ev.headline.pace }
  return [1, -1].map(sign => leverOf(ev, probs, ev.pace, sign as 1 | -1, base, recordOf(g => g.game.pace)))
}

/** The pace candidate that would be listed as an objective (the one that adds most, if it adds a point of probability), or none. */
export const bestPaceLever = (candidates: Lever[]): Lever | null => candidates.filter(l => l.gain >= MIN_GAIN).sort((a, b) => b.gain - a.gain)[0] ?? null

/** The objectives of an own team in a matchup: up to three of attack and three of defence, each worth at least a point of probability, and the pace as information. */
export function leversOf(model: ForecastModel, ev: Evaluation): Levers {
  const { probs, recordOf } = context(model, ev)
  const sideValue = (home: boolean, game: GameResult, kind: 'attack' | 'defence', factor: FactorKey): number => {
    const row = home ? game.homeRow! : game.awayRow!
    return kind === 'attack' ? factors(boxOf(row, 'own'), boxOf(row, 'opp'))[factor] : factors(boxOf(row, 'opp'), boxOf(row, 'own'))[factor]
  }
  const factorLevers = (kind: 'attack' | 'defence'): Lever[] => FACTOR_KEYS
    .map(factor => leverOf(ev, probs, (kind === 'attack' ? ev.fOwn : ev.fRiv).map(f => f[factor]), (GOOD_UP[factor] === (kind === 'attack') ? 1 : -1),
      { side: kind, factor, expected: (kind === 'attack' ? ev.expectedOwn : ev.expectedRival)[factor] }, recordOf(g => sideValue(g.home, g.game, kind, factor))))
    .filter(l => l.gain >= MIN_GAIN).sort((a, b) => b.gain - a.gain).slice(0, PER_SIDE)
  const [fast, slow] = paceCandidates(model, ev)
  return { attack: factorLevers('attack'), defence: factorLevers('defence'), pace: { expected: ev.headline.pace, slow: { threshold: slow.threshold, record: slow.record }, fast: { threshold: fast.threshold, record: fast.record } } }
}
