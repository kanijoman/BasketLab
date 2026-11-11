import { describe, expect, it } from 'vitest'
import { DEFAULT_PACE, HOME_PRIOR, HOME_WEIGHT, NOISE, P0, Q_GAME, TeamRatings } from './teamRatings'
import vectors from '../../../tests/local_vectors/forecast.json'

// The Bayesian (Kalman) rating of the teams: `live_prep.team_rating.TeamRatings` is the reference. Every step of the real games of both fixture leagues (FEB and FBCYL, the latter with a tied game)
// and the gap per 100 possessions at several paces come from calling it (tests/local_vectors/forecast.json).
type Step = { home: string; away: string; margin: number; home_advantage: number; after: Record<string, { mean: number; var: number }> }
type Gap = { own: string; rival: string; pace: number; gap100: number }

it('has the constants of the Python module', () => {
  const c = vectors.constants.team_ratings
  expect({ P0, Q_GAME, NOISE, HOME_PRIOR, HOME_WEIGHT, DEFAULT_PACE }).toEqual({ P0: c.P0, Q_GAME: c.Q_GAME, NOISE: c.NOISE, HOME_PRIOR: c.HOME_PRIOR, HOME_WEIGHT: c.HOME_WEIGHT, DEFAULT_PACE: c.DEFAULT_PACE })
})

describe.each(vectors.competitions.map(c => [c.league, c] as const))('%s: the ratings after every result are the ones of Python', (_league, competition) => {
  it('mean, variance and home court after each game', () => {
    const ratings = new TeamRatings()
    for (const step of competition.ratings.steps as Step[]) {
      ratings.update(step.home, step.away, step.margin)
      expect(ratings.homeAdvantage()).toBeCloseTo(step.home_advantage, 12)
      for (const [team, want] of Object.entries(step.after)) {
        expect(ratings.rating(team)).toBeCloseTo(want.mean, 10)
        expect(ratings.variance(team)).toBeCloseTo(want.var, 10)
      }
    }
  })

  it('the gap per 100 possessions at any pace, a pace that is zero or negative being the default one', () => {
    const ratings = new TeamRatings()
    for (const step of competition.ratings.steps as Step[]) ratings.update(step.home, step.away, step.margin)
    for (const g of competition.gaps as Gap[]) expect(ratings.gapPer100(g.own, g.rival, g.pace)).toBeCloseTo(g.gap100, 10)
  })
})

describe('the rating of a team', () => {
  it('a team never seen is average with the variance of the prior, and ids are compared as texts (FBCYL has numbers)', () => {
    const ratings = new TeamRatings()
    expect(ratings.rating('x')).toBe(0)
    expect(ratings.variance('x')).toBe(P0)
    ratings.update(34001 as unknown as string, 34002 as unknown as string, 10)
    expect(ratings.rating('34001')).toBeGreaterThan(0)
    expect(ratings.rating(34001 as unknown as string)).toBe(ratings.rating('34001'))
  })

  it('a tied game moves the home team down: it underperformed the home court prior', () => {
    const ratings = new TeamRatings()
    ratings.update('A', 'B', 0)
    expect(ratings.rating('A')).toBeLessThan(0)
    expect(ratings.rating('A')).toBe(-ratings.rating('B'))
  })

  it('does not share state between instances', () => {
    const a = new TeamRatings()
    a.update('A', 'B', 20)
    expect(new TeamRatings().rating('A')).toBe(0)
  })
})
