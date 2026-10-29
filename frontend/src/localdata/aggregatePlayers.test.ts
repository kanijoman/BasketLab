import { describe, expect, it } from 'vitest'
import { aggregatePlayers, type PlayerGameRow } from './aggregatePlayers'
import type { GameRow, TeamTableFilter } from './aggregateTeams'
import players from '../../../tests/local_vectors/players_feb.json'
import teams from '../../../tests/local_vectors/team_stats_feb.json'

// Parity of the local player tables (issue #327): the rows summed on the device (with the advanced figures from the season-wide team context)
// must give what GET /players/{collection} answered for the same filter. Reference: `tests/local_vectors/generate.py`.
type Row = Record<string, unknown>
const playerRows = players.rows as unknown as PlayerGameRow[]
const teamRows = teams.rows as unknown as GameRow[]

describe('aggregatePlayers: the player tables from the rows of the contract (issue #327)', () => {
  it.each(players.cases.map(c => [c.name, c] as const))('%s: figures equal the API', (_name, c) => {
    const got = aggregatePlayers(playerRows, teamRows, c.filter as TeamTableFilter & { team?: string }) as unknown as Row[]
    const want = c.players as unknown as Row[]
    expect(got.map(p => `${p.team_name}/${p.player_id}`)).toEqual(want.map(p => `${p.team_name}/${p.player_id}`))   // same order: team, then points
    want.forEach((expected, i) => {
      for (const [key, value] of Object.entries(expected)) {
        if (typeof value === 'number') expect(got[i][key] as number, `${String(expected.player_id)} ${key}`).toBeCloseTo(value, 9)
        else expect(got[i][key], `${String(expected.player_id)} ${key}`).toEqual(value)
      }
    })
  })

  it('no rows is an empty table', () => {
    expect(aggregatePlayers([], teamRows, {})).toEqual([])
  })

  it('a team the context does not know gets the zero defaults, under the keys of the normal path', () => {
    const lone = playerRows.filter(r => r.team_id === playerRows[0].team_id)
    const [player] = aggregatePlayers(lone, [], {}) as unknown as Array<Record<string, unknown>>
    expect([player.usage_pct, player.orating, player.pie, player.tov_pct_adv, player.net_rtg]).toEqual([0, 0, 0, 0, 0])
  })

  it('a team written with another spelling in some games keeps its context: it is looked up by the team id (issue #647 regression)', () => {
    const id = playerRows[0].team_id
    const respelled = playerRows.map(r => (r.team_id === id ? { ...r, team_name: `${r.team_name} ` } : r))
    const mine = (aggregatePlayers(respelled, teamRows, {}) as unknown as Row[]).filter(p => p.team_id === id)
    expect(mine.length).toBeGreaterThan(0)
    for (const p of mine) if ((p.total_minutes as number) > 0) expect(p.usage_pct, String(p.player_id)).toBeGreaterThan(0)
  })
})
