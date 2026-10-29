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

  // Bug #652: the identity of a player is his id within the team; a team written with another spelling or a corrected name is not another player.
  describe('one row per player whatever the spelling (issue #652)', () => {
    const id = playerRows[0].team_id
    const mine = playerRows.filter(r => r.team_id === id)
    const respelled = playerRows.map(r => (r.team_id === id && mine.indexOf(r) % 2 === 1 ? { ...r, team_name: `${r.team_name} `, player_name: `${r.player_name} (corregido)` } : r))

    it('a player written under two team spellings and two names is one row with all his games', () => {
      const before = (aggregatePlayers(playerRows, teamRows, {}) as unknown as Row[]).filter(p => p.team_id === id)
      const after = (aggregatePlayers(respelled, teamRows, {}) as unknown as Row[]).filter(p => p.team_id === id)
      expect(after.length).toBeLessThanOrEqual(before.length)                             // never more rows than players
      expect(new Set(after.map(p => p.player_id)).size).toBe(after.length)                // and none twice
      const games = (rows: Row[]) => rows.reduce((n, p) => n + (p.games_played as number), 0)
      expect(games(after)).toBe(games(before))                                            // merged, not lost
    })

    it('the name and the team name shown are those of his last game', () => {
      const games = playerRows.filter(r => r.player_id === playerRows[0].player_id && r.team_id === id)       // in play order: the fixture's ids grow with the date
      expect(games.length).toBeGreaterThan(1)
      const spelled = games.map((r, i) => (i === games.length - 1 ? { ...r, team_name: 'NUEVO NOMBRE ', player_name: 'J. NUEVO' } : r))
      const [row] = aggregatePlayers(spelled, teamRows, {}) as unknown as Row[]
      expect([row.player_name, row.team_name]).toEqual(['J. NUEVO', 'NUEVO NOMBRE '])
    })

    it('a player who changed team is one row per team', () => {
      const stint = { ...mine[0], team_id: 'OTRO', team_name: 'OTRO EQUIPO' }
      const rows = aggregatePlayers([...mine, stint], teamRows, {}) as unknown as Row[]
      expect(rows.filter(p => p.player_id === mine[0].player_id).map(p => p.team_id).sort()).toEqual([id, 'OTRO'].sort())
    })
  })
})
