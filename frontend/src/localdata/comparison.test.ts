import { describe, expect, it } from 'vitest'
import { compareTeams } from './comparison'
import type { GameRow } from './aggregateTeams'
import febTeams from '../../../tests/local_vectors/team_stats_feb.json'
import fbcylTeams from '../../../tests/local_vectors/team_stats_fbcyl.json'
import febCases from '../../../tests/local_vectors/comparison_feb.json'
import fbcylCases from '../../../tests/local_vectors/comparison_fbcyl.json'

// Comparativas on the device (issue #670): home vs away, won vs lost and a stretch vs the rest of the season, from the rows of the contract. The reference is
// Python's `TeamComparisonService` (`tests/local_vectors/generate.py`) over the real pipelines of each league.
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }

/** Same shape, same strings, numbers equal to the 4 decimals the differences are rounded to (the sums may differ in the last bit between Python and JS). */
function expectSame(actual: unknown, expected: Json, path = '$'): void {
  if (typeof expected === 'number') {
    expect(typeof actual, path).toBe('number')
    expect(actual as number, path).toBeCloseTo(expected, 4)
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

describe.each([['FEB', febTeams.rows, febCases.cases], ['FBCYL', fbcylTeams.rows, fbcylCases.cases]] as const)('%s: the comparison equals what the API answers', (_league, rows, cases) => {
  it.each(cases.map(c => [c.name, c] as const))('%s', (_name, c) => {
    const range = c.range as { from?: string; to?: string }
    expectSame(compareTeams(rows as unknown as GameRow[], c.by as 'venue' | 'result' | 'period', range), c.expected as unknown as Json)
  })
})

describe('compareTeams: what it cannot answer is left to the API (null)', () => {
  const rows = febTeams.rows as unknown as GameRow[]

  it('a stretch with no date at all, and a comparison that does not exist', () => {
    expect(compareTeams(rows, 'period', {})).toBeNull()
    expect(compareTeams(rows, 'period')).toBeNull()
    expect(compareTeams(rows, 'nonsense' as never)).toBeNull()
  })

  it('a game whose date cannot be read is in the rest of the season (Mongo: $not matches a null date) and never in the stretch', () => {
    const broken = rows.map((r, i) => (i === 0 ? { ...r, starttime: 'sin fecha' } : r))
    const total = (by: 'a' | 'b') => compareTeams(broken, 'period', { from: '2000-01-01' })!.team.reduce((n, t) => n + (by === 'a' ? t.games_a : t.games_b), 0)
    expect(total('a')).toBe(23)
    expect(total('b')).toBe(1)
  })

  it('no rows is no teams, not an error', () => {
    expect(compareTeams([], 'venue')).toEqual({ by: 'venue', label_a: 'Local', label_b: 'Visitante', team: [], opponent: [] })
  })
})
