// The walk-forward evaluation of the projection of a match (#938). Every projection is made with the games BEFORE the one it is judged on, from the side of both teams, and answers:
//  - the probability with conditions: for every variable (in a direction and at a share of the scenarios drawn for that game) and for some pairs, the probability of winning in the games where
//    they happen, against whether the game that was played met them and who won (calibration and Brier against the headline, as the objectives were judged on 11/11/2026);
//  - the rest of the game: knowing one variable of the game that was played (its possessions, the points of one side), what the projection foresees of the others, against what was expected
//    without knowing it, with the league layer and with the layer of each team at several shrinkages.
// And, over each whole season: how the game moves with the pace in the league, and whether the slope of each team is its own (the correlation of the slopes of its odd and its even games).
import type { FactorKey } from '../factors'
import type { GameResult } from '../gameLog'
import { quantile } from '../levers'
import { buildModel } from '../pool'
import { MIN_POOL } from '../preview'
import { hashSeed, mulberry32 } from '../prng'
import { buildProjection, type Projection } from '../projection/build'
import { PACE_SHRINK_GAMES, paceResponse, RESPONSE_KEYS, type ResponseKey, type Slopes } from '../projection/paceResponse'
import { project, type ProjectionResult } from '../projection/project'
import { gameValue, meets, VARIABLES, variableOf, type Condition, type VariableId } from '../projection/variables'

export type Layer = 'liga' | 'equipo'

export interface ConditionRecord {
  k: number
  /** The side the conditions are asked from: `own` the home team of the game, `rival` the away team. */
  court: 'own' | 'rival'
  layer: Layer
  conditions: Condition[]
  /** The share of the scenarios the threshold was put at (the product for a pair). */
  target: number
  mass: number
  pWin: number
  headline: number
  met: boolean
  y: number
}

export interface PredictionRecord { k: number; court: 'own' | 'rival'; layer: string; given: VariableId; target: VariableId; predicted: number; actual: number }

export interface ProjectionStudy { conditions: ConditionRecord[]; predictions: PredictionRecord[]; skipped: number }

export interface ProjectionOptions { from?: number; every?: number; ks?: number[] }

const MASSES = [0.05, 0.1, 0.25, 0.5]
const PAIRS = 3
const GIVEN: VariableId[] = ['game.possessions', 'own.points', 'rival.points']

/** What each scenario of a projection says of a variable (for the points, their mean), to put a threshold where a share of the scenarios begins. */
function scenarioValues(p: Projection, id: VariableId): number[] {
  const v = variableOf(id)
  if (v.measure === 'possessions') return p.possessions
  const points = v.side === 'own' ? p.ownPoints : p.rivalPoints
  if (v.measure === 'points') return points
  if (v.measure === 'oer') return points.map((x, i) => (100 * x) / (p.possessions[i] * p.minutes[i]))
  return (v.side === 'own' ? p.fOwn : p.fRiv).map(f => f[v.measure as FactorKey])
}

/** «More than» where the top `mass` of the scenarios begins, or «less than» where the bottom one ends; the points, whole. */
function conditionAt(p: Projection, id: VariableId, op: Condition['op'], mass: number): Condition {
  const cut = quantile(scenarioValues(p, id), op === 'gt' ? 1 - mass : mass)
  return { variable: id, op, value: variableOf(id).measure === 'points' ? Math.round(cut) : cut }
}

/** The questions asked of one side of one game: every variable once (direction and share drawn with a seed of the game) and a few pairs at half and half. */
function questionsOf(p: Projection, seed: string): { conditions: Condition[]; target: number }[] {
  const rand = mulberry32(hashSeed(seed))
  const pick = <T>(xs: T[]): T => xs[Math.floor(rand() * xs.length)]
  const ops: Condition['op'][] = ['gt', 'lt']
  const singles = VARIABLES.map(v => { const mass = pick(MASSES); return { conditions: [conditionAt(p, v.id, pick(ops), mass)], target: mass } })
  const pairs = Array.from({ length: PAIRS }, () => {
    const a = pick(VARIABLES).id
    const b = pick(VARIABLES.filter(v => v.id !== a)).id
    return { conditions: [conditionAt(p, a, pick(ops), 0.5), conditionAt(p, b, pick(ops), 0.5)], target: 0.25 }
  })
  return [...singles, ...pairs]
}

/** A band around the value the game had: ±1 possession, or the points within 2 of what it scored. */
function bandOf(id: VariableId, value: number): Condition[] {
  const half = variableOf(id).measure === 'points' ? 3 : 1
  return [{ variable: id, op: 'gt', value: value - half }, { variable: id, op: 'lt', value: value + half }]
}

/** The projection of the games from `from` on, every `every` games, each with the model of the games before it, judged against the game. */
export function walkForwardProjection(games: GameResult[], gender: string | undefined, { from = 40, every = 4, ks = [5, 20, 80] }: ProjectionOptions = {}): ProjectionStudy {
  const study: ProjectionStudy = { conditions: [], predictions: [], skipped: 0 }
  for (let k = from; k < games.length; k += every) {
    const g = games[k]
    if (!g.homeRow || !g.awayRow) continue
    const model = buildModel(games.slice(0, k), gender)
    if (model.pool.length < MIN_POOL) { study.skipped++; continue }
    const main = paceResponse(model, PACE_SHRINK_GAMES)
    const responses = ks.map(n => [n, paceResponse(model, n)] as const)
    for (const [team, rival, court] of [[g.home, g.away, 'own'], [g.away, g.home, 'rival']] as const) {
      const league = buildProjection(model, team, rival, court)!
      const layered = buildProjection(model, team, rival, court, { paceResponse: main })!
      const actual = (id: VariableId): number => gameValue(g, team, id)!
      const y = g.tied ? 0.5 : (court === 'own' ? g.margin : -g.margin) > 0 ? 1 : 0
      for (const { conditions, target } of questionsOf(league, `${k}|${court}`)) {
        for (const [layer, p] of [['liga', league], ['equipo', layered]] as const) {
          const r = project(p, conditions)
          if (!(r.mass > 0)) continue
          study.conditions.push({ k, court, layer, conditions, target, mass: r.mass, pWin: r.pWin, headline: p.headline.p, met: conditions.every(c => meets(actual(c.variable), c)), y })
        }
      }
      const unconditional = project(league, [])
      for (const given of GIVEN) {
        const band = bandOf(given, actual(given))
        const answers: [string, ProjectionResult][] = [['ninguna', unconditional], ['liga', project(league, band)],
          ...responses.map(([n, response]): [string, ProjectionResult] => [`equipo k=${n}`, project(buildProjection(model, team, rival, court, { paceResponse: response })!, band)])]
        for (const [layer, r] of answers) {
          if (!(r.mass > 0)) continue
          for (const row of r.profile) {
            if (row.variable !== given) study.predictions.push({ k, court, layer, given, target: row.variable, predicted: layer === 'ninguna' ? row.expected : row.given, actual: actual(row.variable) })
          }
        }
      }
    }
  }
  return study
}

/** Pearson's correlation; NaN when one of the two does not vary. */
export function pearson(xs: number[], ys: number[]): number {
  const n = xs.length
  const [mx, my] = [xs.reduce((a, b) => a + b, 0) / n, ys.reduce((a, b) => a + b, 0) / n]
  let [sxy, sxx, syy] = [0, 0, 0]
  for (let i = 0; i < n; i++) {
    sxy += (xs[i] - mx) * (ys[i] - my)
    sxx += (xs[i] - mx) ** 2
    syy += (ys[i] - my) ** 2
  }
  return sxx > 0 && syy > 0 ? sxy / Math.sqrt(sxx * syy) : NaN
}

/** How each thing moves in the league per unit of pace over the usual one (`rho − 1`), over a whole season. */
export const leaguePaceSlopes = (games: GameResult[], gender: string | undefined): Slopes => paceResponse(buildModel(games, gender)).league

export type Reliability = Record<ResponseKey, { attack: number; defence: number }>

/** The correlation, over the teams, of the slope of each team from its odd games with the one from its even games (in the order of the season). */
export function splitHalf(games: GameResult[], gender: string | undefined): Reliability {
  const halves = [games.filter((_, i) => i % 2 === 1), games.filter((_, i) => i % 2 === 0)].map(half => {
    const model = buildModel(half, gender)
    return { response: paceResponse(model), teams: new Set(model.pool.map(s => s.own)) }
  })
  const teams = [...halves[0].teams].filter(t => halves[1].teams.has(t)).sort()
  return Object.fromEntries(RESPONSE_KEYS.map(key => [key, Object.fromEntries((['attack', 'defence'] as const).map(side =>
    [side, pearson(teams.map(t => halves[0].response.raw(t)[side][key]), teams.map(t => halves[1].response.raw(t)[side][key]))]))])) as Reliability
}
