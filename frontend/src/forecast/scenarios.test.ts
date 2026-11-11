import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel, expectedFactors, type ForecastModel } from './pool'
import { bucketsOf, density, evaluate } from './scenarios'
import { headline, type Court } from './winProb'
import { matchupPace } from './gameLog'
import { FACTOR_KEYS } from './factors'
import { phi } from './normal'
import { fbcyl, lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// The scenarios of a matchup, played on the REAL games of the competition: every game of the season gives a scenario (what each side did compared with what it was expected to do, and how the margin
// went compared with what the ratings said), and the pool is anchored so that it gives EXACTLY the win probability of the headline. Real competitions: a complete men's season, an early women's
// one with calendar results the rows lack, and an FBCYL group.
const complete = () => {
  const f = primera()
  const games = buildGames(f.team_rows)
  return { model: buildModel(games, f.gender), games }
}
const early = () => {
  const f = lfChallenge()
  const games = buildGames(f.team_rows, lfChallengeCalendar())
  return { model: buildModel(games, f.gender), games }
}

/** The strongest and the weakest team by rating, and a middling pair. */
function teamsBy(model: ForecastModel) {
  const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))].sort((a, b) => model.ratings.rating(b) - model.ratings.rating(a))
  return { best: ids[0], worst: ids[ids.length - 1], mid: [ids[Math.floor(ids.length / 2)], ids[Math.floor(ids.length / 2) + 1]] as const }
}

const COURTS: Court[] = ['own', 'rival', 'neutral']

describe('the pool of scenarios of a season', () => {
  it('has two scenarios per game with rows, one from each side, and none for a result that only the calendar has', () => {
    const { model } = early()
    expect(model.games).toHaveLength(47)
    expect(model.pool).toHaveLength(2 * 39)
  })

  it('is mirror symmetric: swapping the sides of a scenario gives another scenario of the pool, so nobody is favoured by the way the pool was built', () => {
    const { model } = complete()
    const sum = (x: number[]) => x.reduce((a, b) => a + b, 0)
    expect(sum(model.pool.map(s => s.z))).toBeCloseTo(0, 6)
    for (const k of FACTOR_KEYS) expect(sum(model.pool.map(s => s.dOwn[k])) - sum(model.pool.map(s => s.dRiv[k]))).toBeCloseTo(0, 6)
  })

  it('what the pool says about a factor is in the range of the factor (the residuals are small next to the factors)', () => {
    const { model } = complete()
    for (const s of model.pool) for (const k of FACTOR_KEYS) expect(Math.abs(s.dOwn[k])).toBeLessThan(0.6)
    expect(model.pool.every(s => s.rho > 0.4 && s.rho < 1.8)).toBe(true)
  })

  it('a team without rows has the level of the league, so its matchups expect the league average of everything', () => {
    const { model } = early()
    const unseen = model.level('nobody')
    expect(unseen.attack).toEqual(model.league)
    expect(unseen.defence).toEqual(model.league)
    const e = expectedFactors(unseen, unseen, model.league)
    for (const k of FACTOR_KEYS) expect(e[k]).toBeCloseTo(model.league[k], 12)
  })

  it('has no scenarios when nothing was played, and then there is no evaluation', () => {
    const model = buildModel([], 'F')
    expect(model.pool).toEqual([])
    expect(evaluate(model, 'A', 'B', 'neutral')).toBeNull()
  })
})

describe.each([['a complete men season', complete], ['an early women season with calendar results', early]] as const)('%s', (_name, make) => {
  const { model } = make()
  const { best, worst, mid } = teamsBy(model)
  const matchups = [[best, worst], [worst, best], [mid[0], mid[1]]] as const

  it.each(matchups.flatMap(([a, b]) => COURTS.map(c => [a, b, c] as const)))('the anchored pool gives the headline probability: %s vs %s on %s court', (own, rival, court) => {
    const ev = evaluate(model, own, rival, court)!
    expect(ev.anchored).toBe(true)
    const buckets = bucketsOf(ev)
    expect(buckets[2].p + buckets[3].p).toBeCloseTo(ev.headline.p, 6)
  })

  it.each(matchups)('the four buckets are a distribution and the wins add up to the headline: %s vs %s', (own, rival) => {
    const ev = evaluate(model, own, rival, 'own')!
    const buckets = bucketsOf(ev)
    expect(buckets.map(b => b.id)).toEqual(['lossBig', 'lossClose', 'winClose', 'winBig'])
    expect(buckets.reduce((s, b) => s + b.p, 0)).toBeCloseTo(1, 9)
    expect(buckets[2].p + buckets[3].p).toBeCloseTo(ev.headline.p, 6)
    expect(buckets.every(b => b.p > 0)).toBe(true)
  })

  it.each(matchups)('swapping the teams (and the court) gives the complement and the mirrored buckets: %s vs %s', (own, rival) => {
    const a = evaluate(model, own, rival, 'own')!
    const b = evaluate(model, rival, own, 'rival')!
    expect(a.headline.p + b.headline.p).toBeCloseTo(1, 9)
    const [x, y] = [bucketsOf(a), bucketsOf(b)]
    for (let i = 0; i < 4; i++) expect(x[i].p).toBeCloseTo(y[3 - i].p, 6)
  })

  it('the spread of the pool plus the kernel is the spread of a game of the family, unless the pool is already wider (then the floor of the kernel)', () => {
    const ev = evaluate(model, best, worst, 'neutral')!
    const total = Math.sqrt(ev.residualSd ** 2 + ev.sigmaU ** 2)
    expect(ev.sigmaU).toBeGreaterThanOrEqual(3)
    expect(total).toBeCloseTo(Math.max(ev.headline.sigma, Math.sqrt(ev.residualSd ** 2 + 9)), 6)
  })

  it('the density over the whole margins is a distribution (the tails beyond +-40 are the rest) and its mass on our side of zero, the half of the tied bin included, is the headline', () => {
    const ev = evaluate(model, mid[0], mid[1], 'own')!
    const d = density(ev)
    expect(d[0].margin).toBe(-40)
    expect(d[d.length - 1].margin).toBe(40)
    expect(d.reduce((s, x) => s + x.p, 0)).toBeGreaterThan(0.98)
    const ahead = d.filter(x => x.margin > 0).reduce((s, x) => s + x.p, 0) + d.find(x => x.margin === 0)!.p / 2
    const tail = ev.mean.reduce((sum, m) => sum + 1 - phi((40.5 - m) / ev.sigmaU), 0) / ev.mean.length          // wins by more than 40, outside the chart
    expect(ahead + tail).toBeCloseTo(ev.headline.p, 3)          // the tied bin is split in half: the density is of whole margins
  })

  it('the factor profile of a big win has a better eFG for us and a worse one for the rival than that of a big loss', () => {
    const ev = evaluate(model, mid[0], mid[1], 'own')!
    const [lossBig, , , winBig] = bucketsOf(ev)
    expect(winBig.profile.own.efg).toBeGreaterThan(lossBig.profile.own.efg)
    expect(winBig.profile.rival.efg).toBeLessThan(lossBig.profile.rival.efg)
  })

  it('every bucket highlights the two things that set it apart, the biggest first', () => {
    const ev = evaluate(model, mid[0], mid[1], 'own')!
    for (const b of bucketsOf(ev)) {
      expect(b.highlights).toHaveLength(2)
      expect(Math.abs(b.highlights[0].z)).toBeGreaterThanOrEqual(Math.abs(b.highlights[1].z))
    }
  })
})

describe('the matchups that are not like the rest', () => {
  it('a team the competition has not seen (a promoted one with no games) is a matchup of the league average', () => {
    const { model } = early()
    const ev = evaluate(model, 'nobody', 'nobody-else', 'neutral')!
    expect(ev.headline.p).toBe(0.5)
    const [a, b, c, d] = bucketsOf(ev).map(x => x.p)
    expect(a).toBeCloseTo(d, 6)
    expect(b).toBeCloseTo(c, 6)
  })

  it('FBCYL is played the same way with ids that are numbers in the rows', () => {
    const f = fbcyl()
    const model = buildModel(buildGames(f.team_rows), f.gender)
    const { best, worst } = teamsBy(model)
    const ev = evaluate(model, best, worst, 'own')!
    expect(bucketsOf(ev).reduce((s, b) => s + b.p, 0)).toBeCloseTo(1, 9)
    expect(ev.headline.sigma).toBe(14)
  })

  it('the headline of the evaluation is the one of the rating model at the pace of the matchup', () => {
    const { model, games } = complete()
    const { best, worst } = teamsBy(model)
    const ev = evaluate(model, best, worst, 'own')!
    expect(ev.headline).toEqual(headline({ ratings: model.ratings, own: best, rival: worst, court: 'own', pace: matchupPace(games, best, worst), gender: 'M' }))
  })
})
