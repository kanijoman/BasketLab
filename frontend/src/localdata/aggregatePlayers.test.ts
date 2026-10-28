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

  it('a team the context does not know gets zero advanced figures, as the service does', () => {
    const lone = playerRows.filter(r => r.team_id === playerRows[0].team_id)
    const [player] = aggregatePlayers(lone, [], {})
    expect([player.usage_pct, player.orating, player.pie]).toEqual([0, 0, 0])
  })
})
