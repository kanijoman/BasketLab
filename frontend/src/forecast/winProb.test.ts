import { describe, expect, it } from 'vitest'
import { headline, wpParams, Z80 } from './winProb'
import { TeamRatings } from './teamRatings'
import { pyRound } from '@/localdata/pyMath'
import vectors from '../../../tests/local_vectors/forecast.json'

// The win probability at tip-off: `live_core.win_prob.WinProbabilityModel.evaluate` with the matchup prior of the package (`net_rtg_prior` = the rounded gap at the pace of the matchup) and the
// home court of the family of the competition (`WP_BY_GENDER`), over the Kalman ratings of the real games of each fixture league. Python rounds what it answers; the engine keeps the exact
// numbers, so they are compared once rounded the same way.
type Case = { own: string; rival: string; gender: string; court: 'own' | 'rival' | 'neutral'; pace: number; gap100: number; p: number; projected_margin: number; sd: number; poss_remaining: number; mu_per_100: number }

it('the calibrated parameters of each family, and the neutral ones for a competition that does not say it', () => {
  const v = vectors.constants.win_prob
  expect(wpParams('F')).toEqual({ sigma: v.F.sigma, homeAdv: v.F.home_adv })
  expect(wpParams('M')).toEqual({ sigma: v.M.sigma, homeAdv: v.M.home_adv })
  expect(wpParams(undefined)).toEqual({ sigma: v.default.sigma, homeAdv: v.default.home_adv })
  expect(wpParams('X')).toEqual(wpParams(undefined))
})

describe.each(vectors.competitions.map(c => [c.league, c] as const))('%s: the headline is the one of Python', (_league, competition) => {
  const ratings = new TeamRatings()
  for (const s of competition.ratings.steps) ratings.update(s.home, s.away, s.margin)

  it.each((competition.headline as Case[]).map(c => [`${c.own}-${c.rival} ${c.gender || 'sin género'} ${c.court} ritmo ${c.pace}`, c] as const))('%s', (_name, c) => {
    const got = headline({ ratings, own: c.own, rival: c.rival, court: c.court, pace: c.pace, gender: c.gender || undefined })
    expect(pyRound(got.gap100, 3)).toBe(c.gap100)
    expect(pyRound(got.p, 4)).toBe(c.p)
    expect(pyRound(got.mu, 2)).toBe(c.projected_margin)
    expect(pyRound(got.sigma, 2)).toBe(c.sd)
    expect(pyRound(got.pace, 1)).toBe(c.poss_remaining)
  })
})

describe('the headline', () => {
  const ratings = new TeamRatings()
  ratings.update('A', 'B', 15)

  it('two teams with nothing between them on a neutral court are a coin toss, and the 80 % range is symmetric around the expected margin', () => {
    const h = headline({ ratings: new TeamRatings(), own: 'A', rival: 'B', court: 'neutral', pace: 70 })
    expect(h.p).toBe(0.5)
    expect(h.mu).toBe(0)
    expect(h.range80).toEqual([-Z80 * h.sigma, Z80 * h.sigma])
  })

  it('the home court helps whoever has it and swapping the teams gives the complement', () => {
    const own = headline({ ratings, own: 'A', rival: 'B', court: 'own', pace: 70, gender: 'F' })
    const rival = headline({ ratings, own: 'A', rival: 'B', court: 'rival', pace: 70, gender: 'F' })
    const swapped = headline({ ratings, own: 'B', rival: 'A', court: 'rival', pace: 70, gender: 'F' })
    expect(own.p).toBeGreaterThan(rival.p)
    expect(swapped.p).toBeCloseTo(1 - own.p, 12)
  })

  it('the unknown pace is 70 possessions and says so', () => {
    expect(headline({ ratings, own: 'A', rival: 'B', court: 'own', pace: 0 }).pace).toBe(70)
  })
})
