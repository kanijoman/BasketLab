// A question to the projection of a match (#936): in the games like this one where every condition holds, how often that happens, how often we win, what the rest of those games looks like
// (against what is expected of the matchup) and how the season went in our games that met them. CONDITIONAL: it describes those games, it does not say that making it happen wins (study of
// 26/10/2026: no evidence that correcting something during a game changes what follows). Without enough games like it (under 5 of every 100) or without the support of the evaluation, the
// probability is not a figure to show (`figure` null).
import { gamesOf } from '../gameLog'
import type { ForecastModel } from '../pool'
import type { Projection } from './build'
import { queryOf, scenarioOdds, scenarioValue, scenarioValues, truncatedMean, type ScenarioQuery } from './conditions'
import { gameValue, meets, mirrored, VARIABLES, variableOf, type Condition, type Side, type VariableId } from './variables'

/** Below this share of the games like this one, a condition happens too rarely for its probability to be a figure. */
export const MIN_MASS = 0.05

/** A variable in every game like this one (`expected`) and in those where the conditions hold (`given`), and how much it spreads between the scenarios (to tell what moves most). */
export interface ProfileRow { variable: VariableId; expected: number; given: number; spread: number }

/** Games of the season of a team that met the conditions: how many, how many it won, and their scores (its points first) in the order they were played. */
export interface SeasonRecord { reached: number; won: number; scores: [number, number][] }

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
  record: SeasonRecord
  /** The rival's games of the season in the same situation, with its opponent in our place (the conditions `mirrored`), and the ones it won: what it does when that happens to it. */
  rivalRecord: SeasonRecord
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

/** The games of `team` of the season with a box score that met every condition (from its side: `own` is `team`), and the ones it won. */
export function seasonRecord(model: ForecastModel, team: string, conditions: Condition[]): SeasonRecord {
  const mine = gamesOf(model.games, team).filter(g => g.homeRow && g.awayRow)
  const reached = mine.filter(g => conditions.every(c => { const v = gameValue(g, team, c.variable); return v !== null && meets(v, c) }))
  const scores = reached.map((g): [number, number] => (g.home === team ? [g.homePoints, g.awayPoints] : [g.awayPoints, g.homePoints]))
  return { reached: reached.length, won: scores.filter(([a, b]) => a > b).length, scores }
}

const sd = (xs: number[]): number => { const m = sum(xs) / xs.length; return Math.sqrt(sum(xs.map(x => (x - m) ** 2)) / xs.length) }

/** How much a variable spreads between the scenarios; for the points (and the points per 100 possessions) the kernel around each one too. */
function spreadOf(p: Projection, id: VariableId): number {
  const v = variableOf(id)
  const played = sum(p.possessions.map((n, i) => n * p.minutes[i])) / p.possessions.length
  const within = v.kind === 'scenario' ? 0 : v.measure === 'points' ? p.kernel : (100 * p.kernel) / played
  return Math.sqrt(sd(scenarioValues(p, id)) ** 2 + within ** 2) || 1
}

/** Below this many spreads from the usual a variable has not moved. */
const STILL = 0.1

/** The (up to) two variables that move most in those games, in spreads of the scenarios, leaving out what was asked: the marks of the table of the card. */
export function movers(r: ProjectionResult, n = 2): VariableId[] {
  const asked = new Set(r.conditions.map(c => c.variable))
  const z = (row: ProfileRow): number => Math.abs(row.given - row.expected) / row.spread
  return r.profile.filter(row => !asked.has(row.variable) && z(row) >= STILL).sort((a, b) => z(b) - z(a)).slice(0, n).map(row => row.variable)
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
    profile: VARIABLES.map(v => ({ variable: v.id, expected: before.value(v.id), given: after.value(v.id), spread: spreadOf(p, v.id) })),
    points: {
      own: split(before.points.own, after.points.own, before.played, after.played),
      rival: split(before.points.rival, after.points.rival, before.played, after.played),
    },
    record: seasonRecord(p.model, p.own, conditions),
    rivalRecord: seasonRecord(p.model, p.rival, conditions.map(mirrored)),
  }
}
