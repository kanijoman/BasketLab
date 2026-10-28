import { describe, expect, it } from 'vitest'
import { aggregateTeams, type GameRow, type TeamTableFilter } from './aggregateTeams'
import vectors from '../../../tests/local_vectors/team_stats_feb.json'

// Parity of the local team tables (issue #327): the rows of the contract summed on the device must give what the API answered for the same filter.
// The reference is Python (`tests/local_vectors/generate.py`: the real Mongo pipelines on a 12-game league with stored and estimated possessions).
type Row = Record<string, unknown>
const rows = vectors.rows as unknown as GameRow[]

function expectSameTable(actual: Row[], expected: Row[]) {
  expect(actual.map(r => r.team_name)).toEqual(expected.map(r => r.team_name))      // same teams in the same order (points per game, descending)
  for (const want of expected) {
    const got = actual.find(r => r.team_id === want.team_id) as Row
    expect(got, `team ${String(want.team_id)}`).toBeDefined()
    for (const [key, value] of Object.entries(want)) {
      if (key === '_id') continue
      if (key === 'match_list') expect([...(got[key] as number[])].sort()).toEqual([...(value as number[])].sort())
      else if (typeof value === 'number') expect(got[key] as number, key).toBeCloseTo(value, 9)
      else expect(got[key], key).toEqual(value)
    }
  }
}

describe('aggregateTeams: the team tables from the rows of the contract (issue #327)', () => {
  it.each(vectors.cases.map(c => [c.name, c] as const))('%s: team and rival figures equal the API', (_name, c) => {
    const out = aggregateTeams(rows, c.filter as TeamTableFilter)
    expectSameTable(out.team_stats as unknown as Row[], c.team_stats as unknown as Row[])
    expectSameTable(out.opponent_stats as unknown as Row[], c.opponent_stats as unknown as Row[])
  })

  it('an empty list of rows is an empty table, not an error', () => {
    expect(aggregateTeams([], {})).toEqual({ team_stats: [], opponent_stats: [] })
  })

  it('a team with no possessions has zero ratings rather than NaN (the pipeline divides safely)', () => {
    const lone = rows.filter(r => r.team_id === rows[0].team_id).slice(0, 1).map(r => ({ ...r, possessions: 0, opponent_possessions: 0 }))
    const [team] = aggregateTeams(lone, {}).team_stats
    expect([team.offensive_rating, team.defensive_rating, team.net_rating, team.turnover_rate]).toEqual([0, 0, 0, 0])
  })

  it('a row whose date cannot be read is out of any filtered range, as in Mongo (onError null), and in the unfiltered table', () => {
    const bad = rows.map((r, i) => (i === 0 ? { ...r, starttime: 'sin fecha' } : r))
    const total = (f: TeamTableFilter) => aggregateTeams(bad, f).team_stats.reduce((n, t) => n + t.total_games, 0)
    expect(total({})).toBe(24)
    expect(total({ from: '2000-01-01' })).toBe(23)
  })
})
