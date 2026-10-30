import { describe, expect, it } from 'vitest'
import { byPeriod, derivedCoverage, pointsByOrigin, situations, timeoutEffects, type Derived } from './pbp'
import febVectors from '../../../tests/local_vectors/pbp_feb.json'
import fbcylVectors from '../../../tests/local_vectors/pbp_fbcyl.json'

// Análisis PBP on the device (issue #676): the five tables summed from the `DERIVED` of each game equal what the real services answer
// (`tests/local_vectors/generate.py`: the fixture games with games that are reliable, not reliable, of an older version, doubtful, with an overtime and with no timeouts).
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }

function expectSame(actual: unknown, expected: Json, path = '$'): void {
  if (typeof expected === 'number') {
    expect(typeof actual, path).toBe('number')
    expect(actual as number, path).toBeCloseTo(expected, 9)
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true)
    expect((actual as unknown[]).length, path).toBe(expected.length)
    expected.forEach((item, i) => expectSame((actual as unknown[])[i], item, `${path}[${i}]`))
  } else if (expected !== null && typeof expected === 'object') {
    expect(actual, path).not.toBeNull()
    expect(Object.keys(actual as object).sort(), path).toEqual(Object.keys(expected).sort())
    for (const [key, value] of Object.entries(expected)) expectSame((actual as Record<string, unknown>)[key], value, `${path}.${key}`)
  } else {
    expect(actual, path).toEqual(expected)
  }
}

describe.each([['FEB', febVectors], ['FBCYL', fbcylVectors]] as const)('%s: the pbp tables equal what the API answers', (_league, vectors) => {
  const derived = vectors.derived as unknown as Derived
  const expected = vectors.expected as unknown as Record<string, Json>

  it('points by origin', () => expectSame(pointsByOrigin(derived), expected.origin))
  it('by period (Q1-Q4 and the overtimes together)', () => expectSame(byPeriod(derived), expected.periods))
  it('situations: after a timeout, first possessions, first and last two minutes', () => expectSame(situations(derived), expected.situations))
  it('the effect of the timeouts', () => expectSame(timeoutEffects(derived), expected.timeouts))
  it('the coverage: the games without the DERIVED the tables need, which', () => expectSame(derivedCoverage(derived), expected.coverage))
})

describe('the pbp tables: the corners', () => {
  const none: Derived = { format: 1, collection: 'C', league: 'feb', games: 0, total: 0, without_derived: [], rows: [] }

  it('no game with DERIVED is no table, and the coverage says there is nothing pending', () => {
    expect([pointsByOrigin(none), byPeriod(none), situations(none), timeoutEffects(none)]).toEqual([[], [], [], []])
    expect(derivedCoverage(none)).toEqual({ collection: 'C', min_version: 6, total: 0, pending: 0, pending_games: [] })
  })

  it('the games that are listed as pending are the first 50 in the order of the ids, and the count is the whole', () => {
    const many: Derived = { ...none, total: 60, without_derived: Array.from({ length: 60 }, (_, i) => ({ code: String(100 + i), teams: ['A', 'B'] })) }
    const coverage = derivedCoverage(many)
    expect(coverage.pending).toBe(60)
    expect(coverage.pending_games).toHaveLength(50)
    expect(coverage.pending_games[0].code).toBe('100')
  })

  it('FEB ids sort as numbers, FBCYL ids as text', () => {
    const feb = derivedCoverage({ ...none, without_derived: [{ code: '9', teams: [] }, { code: '10', teams: [] }] })
    expect(feb.pending_games.map(g => g.code)).toEqual(['9', '10'])
    const fbcyl = derivedCoverage({ ...none, league: 'fbcyl', without_derived: [{ code: '9', teams: [] }, { code: '10', teams: [] }] })
    expect(fbcyl.pending_games.map(g => g.code)).toEqual(['10', '9'])
  })
})
