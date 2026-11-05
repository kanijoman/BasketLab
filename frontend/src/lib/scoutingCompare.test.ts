import { describe, expect, it } from 'vitest'
import { STAT_CATALOG, compareTeams } from './scoutingCompare'
import vectors from '../../../tests/local_vectors/scouting_compare.json'

// The matchup of the scouting (our team against the rival, stat by stat) on the device (issue #751): the reference is `live_prep.scouting_compare.compare_teams`,
// whose answers are in tests/local_vectors/scouting_compare.json (regenerated with `python tests/local_vectors/generate.py`). The catalog is the one of the report engine.
type Row = Record<string, unknown>
type Case = { name: string; own: Row | null; rival: Row | null; threshold_pct?: number; expected: unknown[] }

describe('the catalog of stats', () => {
  it('is the one of the report engine, in the same order', () => {
    expect(STAT_CATALOG).toEqual(vectors.catalog)
  })
})

describe('compareTeams answers what the Python answers', () => {
  it.each((vectors.cases as unknown as Case[]).map(c => [c.name, c] as const))('%s', (_name, c) => {
    const got = c.threshold_pct === undefined ? compareTeams(c.own, c.rival) : compareTeams(c.own, c.rival, c.threshold_pct)
    expect(got).toEqual(c.expected)
  })

  it('a team without row, or a missing team, has nothing to compare', () => {
    expect(compareTeams(null, { points_per_game: 80 })).toEqual([])
    expect(compareTeams({ points_per_game: 80 }, undefined)).toEqual([])
    expect(compareTeams({}, {})).toEqual([])
  })

  it('a tie in the rounding of the text goes to the even digit, as Python does (12.25 -> 12.2, 12.35 -> 12.3)', () => {
    const [row] = compareTeams({ points_per_game: 12.25 }, { points_per_game: 12.35 })
    expect([row.own_text, row.rival_text]).toEqual(['12,2', '12,3'])
  })

  it('a zero in the rival is not a division by zero', () => {
    const [row] = compareTeams({ turnovers_per_game: 5 }, { turnovers_per_game: 0 })
    expect(row.diff_pct).toBe(0)
  })
})
