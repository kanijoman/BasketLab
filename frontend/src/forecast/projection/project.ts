// A question to the projection of a match (#936): in the games like this one where every condition holds, how often that happens, how often we win, what the rest of those games looks like
// (against what is expected of the matchup) and how the season went in our games that met them. CONDITIONAL: it describes those games, it does not say that making it happen wins (study of
// 26/10/2026: no evidence that correcting something during a game changes what follows). Without enough games like it (under 5 of every 100) or without the support of the evaluation, the
// probability is not a figure to show (`figure` null).
import { gamesOf } from '../gameLog'
import type { Projection } from './build'
import { queryOf, scenarioOdds, scenarioValue, truncatedMean, type ScenarioQuery } from './conditions'
import { gameValue, meets, VARIABLES, variableOf, type Condition, type Side, type VariableId } from './variables'

/** Below this share of the games like this one, a condition happens too rarely for its probability to be a figure. */
export const MIN_MASS = 0.05

export interface ProfileRow { variable: VariableId; expected: number; given: number }

/**
 * The points of a side in those games against what is expected, split into what the possessions and what the points per 100 possessions give: points = possessions × OER / 100, so
 * ln(given / expected) is the sum of the two logarithms and each gets its share of the difference (the logarithmic mean, exact).
 */
export interface PointsSplit { expected: number; given: number; pace: number; efficiency: number }

export interface ProjectionResult {
  conditions: Condition[]
  /** The share of the games like this one where every condition holds. */
  mass: number
  /** The probability of winning in those games (NaN when there are none). */
  pWin: number
  /** `pWin` when it can be shown: not rare, and every variable backed by the evaluation. */
  figure: number | null
  rare: boolean
  supported: boolean
  /** Every variable: what is expected of this matchup and what it is in those games. */
  profile: ProfileRow[]
  points: Record<Side, PointsSplit>
  /** Our games of the season with a box score that met every condition, and the ones we won. */
  record: { reached: number; won: number }
}

const sum = (xs: number[]): number => xs.reduce((a, b) => a + b, 0)
const EVERY_GAME: ScenarioQuery = { inside: true, own: { lo: -Infinity, hi: Infinity }, rival: { lo: -Infinity, hi: Infinity } }

/** The weighted mean of what each scenario says of every variable, and the possessions they were played at (possessions × minutes, for the points per 100 possessions). */
function means(p: Projection, weights: number[], queries: ScenarioQuery[]) {
  const total = sum(weights)
  const avg = (value: (i: number) => number): number => sum(weights.map((w, i) => (w ? w * value(i) : 0))) / total
  const points = { own: avg(i => truncatedMean(queries[i].own, p.ownPoints[i], p.kernel)), rival: avg(i => truncatedMean(queries[i].rival, p.rivalPoints[i], p.kernel)) }
  const played = avg(i => p.possessions[i] * p.minutes[i])
  const value = (id: VariableId): number => {
    const v = variableOf(id)
    if (v.kind === 'scenario') return avg(i => scenarioValue(p, i, v))
    return v.measure === 'points' ? points[v.side!] : (100 * points[v.side!]) / played
  }
  return { value, points, played }
}

function split(expected: number, given: number, playedBefore: number, playedNow: number): PointsSplit {
  const diff = given - expected
  const lnPoints = Math.log(given / expected)
  const logMean = Math.abs(lnPoints) > 1e-12 ? diff / lnPoints : expected
  const pace = logMean * Math.log(playedNow / playedBefore)
  return { expected, given, pace, efficiency: diff - pace }
}

function recordOf(p: Projection, conditions: Condition[]): ProjectionResult['record'] {
  const mine = gamesOf(p.model.games, p.own).filter(g => g.homeRow && g.awayRow)
  const reached = mine.filter(g => conditions.every(c => { const v = gameValue(g, p.own, c.variable); return v !== null && meets(v, c) }))
  return { reached: reached.length, won: reached.filter(g => (g.home === p.own ? g.margin : -g.margin) > 0).length }
}

/** The answer of the projection `p` to the games where every one of `conditions` holds (none: every game like this one). */
export function project(p: Projection, conditions: Condition[]): ProjectionResult {
  const n = p.ownPoints.length
  const queries = p.ownPoints.map((_, i) => queryOf(p, i, conditions))
  const odds = queries.map((q, i) => scenarioOdds(p, i, q))
  const weights = odds.map(o => o.meets)
  const mass = sum(weights) / n
  const pWin = sum(odds.map(o => o.wins)) / sum(weights)
  const before = means(p, odds.map(() => 1), queries.map(() => EVERY_GAME))
  const after = means(p, weights, queries)
  const rare = !(mass >= MIN_MASS)
  const supported = conditions.every(c => variableOf(c.variable).supported)
  return {
    conditions, mass, pWin, figure: !rare && supported ? pWin : null, rare, supported,
    profile: VARIABLES.map(v => ({ variable: v.id, expected: before.value(v.id), given: after.value(v.id) })),
    points: {
      own: split(before.points.own, after.points.own, before.played, after.played),
      rival: split(before.points.rival, after.points.rival, before.played, after.played),
    },
    record: recordOf(p, conditions),
  }
}
