import { describe, expect, it } from 'vitest'
import { boxOf, factors, leagueFactors, pointsPerUnit, shrunkLevel, sumBoxes, FACTOR_KEYS, FT_POSSESSION_COST, SHRINK_GAMES, WEIGHTS, type Box } from './factors'
import vectors from '../../../tests/local_vectors/forecast.json'

// The four factors of the live engine (`live_core.four_factors`) and the level of a team shrunk to the league (`live_prep.package_builder.shrunk_team_level`), over the REAL rows of the fixture leagues
// (FEB and FBCYL): the stats of a row, the factors of each side, the points a unit of each factor is worth, and the level of every team (tests/local_vectors/forecast.json).
type Case = { row: Parameters<typeof boxOf>[0]; own: Box; opp: Box; factors: Record<string, number>; per_unit: Record<string, number> }

it('the weights, the cost of a free throw in possessions and the shrinkage are the ones of Python', () => {
  const c = vectors.constants.four_factors
  expect({ WEIGHTS, FT_POSSESSION_COST, SHRINK_GAMES }).toEqual({ WEIGHTS: c.weights, FT_POSSESSION_COST: c.ft_possession_cost, SHRINK_GAMES: c.shrink_games })
})

describe.each(vectors.competitions.map(c => [c.league, c] as const))('%s', (_league, competition) => {
  const cases = competition.factors as unknown as Case[]

  it('a row gives the stats the engine uses, own and opponent side (ids may be numbers in FBCYL)', () => {
    for (const c of cases) {
      expect(boxOf(c.row, 'own')).toEqual(c.own)
      expect(boxOf(c.row, 'opp')).toEqual(c.opp)
    }
  })

  it('the four factors of each side of each game', () => {
    for (const c of cases) for (const k of FACTOR_KEYS) expect(factors(c.own, c.opp)[k]).toBeCloseTo(c.factors[k], 12)
  })

  it('the points a unit of each factor is worth', () => {
    for (const c of cases) for (const k of FACTOR_KEYS) expect(pointsPerUnit(c.own)[k]).toBeCloseTo(c.per_unit[k], 9)
  })

  it('the level of every team: its sums over its rows against the league, shrunk by its games', () => {
    const league = leagueFactors(cases.map(c => c.own))
    for (const k of FACTOR_KEYS) expect(league[k]).toBeCloseTo(competition.levels.league[k as keyof typeof competition.levels.league], 12)
    for (const [team, want] of Object.entries(competition.levels.teams)) {
      const mine = cases.filter(c => String(c.row.team_id) === team)
      const level = shrunkLevel({ for: sumBoxes(mine.map(c => c.own)), against: sumBoxes(mine.map(c => c.opp)) }, league, mine.length)
      expect(mine.length).toBe(want.games)
      for (const kind of ['attack', 'defence'] as const) for (const k of FACTOR_KEYS) expect(level[kind][k]).toBe(want.level[kind][k as keyof typeof want.level.attack])
    }
  })
})

describe('the awkward inputs', () => {
  const zero: Box = { fg2m: 0, fg2a: 0, fg3m: 0, fg3a: 0, ftm: 0, fta: 0, orb: 0, drb: 0, tov: 0, pts: 0 }

  it('a side that has done nothing has zero factors, never NaN', () => {
    expect(factors(zero, zero)).toEqual({ efg: 0, tov: 0, orb: 0, ftr: 0 })
  })

  it('too few possessions to estimate the rates use the fallbacks of the engine', () => {
    expect(pointsPerUnit(zero)).toEqual({ efg: 2 * 0.88 * 100, tov: 100, orb: 0.5 * 1.0 * 100, ftr: 0.88 * 0.72 * 100 })
  })

  it('no games is the league, whatever the sums', () => {
    const league = { efg: 0.5, tov: 0.15, orb: 0.3, ftr: 0.25 }
    expect(shrunkLevel({ for: zero, against: zero }, league, 0)).toEqual({ attack: league, defence: league })
  })
})
