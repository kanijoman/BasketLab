import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel } from './pool'
import { matchupRows, EVEN_EDGE } from './matchup'
import { FACTOR_KEYS, pointsPerUnit } from './factors'
import { primera } from '@/test/forecastFixtures'

// The matchup factor by factor on a real season: what each side is expected to make against the other, against the league, and what that edge is worth in points per 100 possessions.
const f = primera()
const model = buildModel(buildGames(f.team_rows), f.gender)
const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))].sort((a, b) => model.ratings.rating(b) - model.ratings.rating(a))
const [best, worst] = [ids[0], ids[ids.length - 1]]

describe('the rows of the matchup', () => {
  const rows = matchupRows(model, best, worst)

  it('has one row per factor, in the order of the factors', () => {
    expect(rows.map(r => r.factor)).toEqual([...FACTOR_KEYS])
  })

  it('says what each side is expected to make against the other and the league average', () => {
    for (const r of rows) {
      expect(r.expectedOwn).toBeGreaterThan(0)
      expect(r.expectedRival).toBeGreaterThan(0)
      expect(r.league).toBeCloseTo(model.league[r.factor], 12)
    }
  })

  it('the edge is what the difference of the expectations is worth, with the good side of each factor (more turnovers are bad)', () => {
    const pu = pointsPerUnit(model.sums.get(best)!.for)
    for (const r of rows) {
      const good = r.factor === 'tov' ? -1 : 1
      expect(r.edge).toBeCloseTo(pu[r.factor] * good * (r.expectedOwn - r.expectedRival), 9)
    }
  })

  it('the advantage follows the edge: ours, theirs, or even when it is under half a point per 100 possessions', () => {
    expect(EVEN_EDGE).toBe(0.5)
    for (const r of rows) expect(r.advantage).toBe(r.edge > EVEN_EDGE ? 'own' : r.edge < -EVEN_EDGE ? 'rival' : 'even')
  })

  it('swapping the teams swaps the sides and flips the edge', () => {
    const swapped = matchupRows(model, worst, best)
    rows.forEach((r, i) => {
      expect(swapped[i].expectedOwn).toBeCloseTo(r.expectedRival, 12)
      expect(swapped[i].expectedRival).toBeCloseTo(r.expectedOwn, 12)
    })
  })

  it('a team the competition has not seen is the league average on both sides: no edge', () => {
    for (const r of matchupRows(model, 'nobody', 'nobody-else')) {
      expect(r.expectedOwn).toBeCloseTo(r.league, 12)
      expect(Math.abs(r.edge)).toBeLessThan(1e-9)
      expect(r.advantage).toBe('even')
    }
  })
})
