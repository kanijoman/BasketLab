// The matchup of the preview factor by factor (#847): what each side is expected to make against the other (what it usually makes plus what the other usually lets, against the league) and
// what that edge is worth in points per 100 possessions (the analytic marginals of the engine: `pointsPerUnit`). A description of the matchup, not a forecast of how it will go.
import { FACTOR_KEYS, pointsPerUnit, type Box, type FactorKey } from './factors'
import { expectedFactors, type ForecastModel } from './pool'

export interface MatchupRow {
  factor: FactorKey
  /** What the own side is expected to make against the rival, what the rival is expected to make against it, and the league average. */
  expectedOwn: number
  expectedRival: number
  league: number
  /** Points per 100 possessions the difference is worth, positive when it favours the own side. */
  edge: number
  advantage: 'own' | 'rival' | 'even'
}

/** An edge under this (points per 100 possessions) is not an advantage for anybody. */
export const EVEN_EDGE = 0.5
const GOOD: Record<FactorKey, 1 | -1> = { efg: 1, tov: -1, orb: 1, ftr: 1 }
const NO_BOX: Box = { fg2m: 0, fg2a: 0, fg3m: 0, fg3a: 0, ftm: 0, fta: 0, orb: 0, drb: 0, tov: 0, pts: 0 }

export function matchupRows(model: ForecastModel, own: string, rival: string): MatchupRow[] {
  const [levelOwn, levelRival] = [model.level(own), model.level(rival)]
  const [eo, er] = [expectedFactors(levelOwn, levelRival, model.league), expectedFactors(levelRival, levelOwn, model.league)]
  const worth = pointsPerUnit(model.sums.get(String(own))?.for ?? NO_BOX)
  return FACTOR_KEYS.map(factor => {
    const edge = worth[factor] * GOOD[factor] * (eo[factor] - er[factor])
    return { factor, expectedOwn: eo[factor], expectedRival: er[factor], league: model.league[factor], edge, advantage: edge > EVEN_EDGE ? 'own' : edge < -EVEN_EDGE ? 'rival' : 'even' }
  })
}
