import { describe, expect, it } from 'vitest'
import { aggregatePlayersFbcyl, type FbcylPlayerGameRow } from './aggregatePlayersFbcyl'
import type { GameRow, TeamTableFilter } from './aggregateTeams'
import players from '../../../tests/local_vectors/players_fbcyl.json'
import teams from '../../../tests/local_vectors/team_stats_fbcyl.json'

// Parity of the FBCYL player table (issue #644): the rows summed on the device must give what GET /players/{collection} answered for the same
// filter. Reference: `tests/local_vectors/generate_fbcyl_players.py` (the real season pipeline on a real mongod, committed).
type Row = Record<string, unknown>
const playerRows = players.rows as unknown as FbcylPlayerGameRow[]
const teamRows = teams.rows as unknown as GameRow[]
const filterOf = (c: (typeof players.cases)[number]) => c.filter as TeamTableFilter & { team?: string }

describe('aggregatePlayersFbcyl: the FBCYL player table from the rows of the contract (issue #644)', () => {
  it.each(players.cases.map(c => [c.name, c] as const))('%s: figures equal the API', (_name, c) => {
    const got = aggregatePlayersFbcyl(playerRows, teamRows, filterOf(c)) as unknown as Row[]
    const want = c.players as unknown as Row[]
    // team, then points: the order the pipeline sorts by (Mongo does not say which of two players with the same points comes first)
    expect(got.map(p => `${p.team_name}/${p.total_pts}`)).toEqual(want.map(p => `${p.team_name}/${p.total_pts}`))
    const byPlayer = new Map(got.map(p => [`${p.team_id}/${p.player_id}`, p]))
    expect(byPlayer.size).toBe(want.length)
    for (const expected of want) {
      const player = byPlayer.get(`${expected.team_id}/${expected.player_id}`) as Row
      expect(player, `${String(expected.player_name)}`).toBeDefined()
      for (const [key, value] of Object.entries(expected)) {
        if (key === 'player_uuid' && String(value).includes(' ')) continue          // the divergence below
        if (typeof value === 'number') expect(player[key] as number, `${String(expected.player_name)} ${key}`).toBeCloseTo(value, 9)
        else expect(player[key], `${String(expected.player_name)} ${key}`).toEqual(value)
      }
    }
  })

  it('DIVERGENCE (more correct than the API): the uuid left out of a game is completed over the whole season, not over the games the filter keeps', () => {
    // With a date range that keeps only the games in which FBCYL left the uuid out, the API falls back to the normalised name as the key
    // ("J ALFA03 PEREZ"); the exporter has completed the real uuid, so the same player has the same key whatever the filter. Same sums.
    const fallbacks = players.cases.flatMap(c => (c.players as unknown as Row[]).filter(p => String(p.player_uuid).includes(' ')))
    expect(fallbacks.length).toBeGreaterThan(0)
    for (const api of fallbacks) {
      const mine = (aggregatePlayersFbcyl(playerRows, teamRows, {}) as unknown as Row[]).find(p => p.team_id === api.team_id && p.player_id === api.player_id)!
      expect(String(mine.player_uuid)).not.toContain(' ')
    }
  })

  it('no rows is an empty table', () => {
    expect(aggregatePlayersFbcyl([], teamRows, {})).toEqual([])
  })

  it('a player whose uuid FBCYL left out of some games is one player, not two', () => {
    const all = aggregatePlayersFbcyl(playerRows, teamRows, {}) as unknown as Row[]
    expect(new Set(all.map(p => `${p.team_id}/${p.player_uuid}`)).size).toBe(all.length)
  })
})
