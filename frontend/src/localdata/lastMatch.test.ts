import { describe, expect, it } from 'vitest'
import { lastMatchOf } from './lastMatch'
import { aggregateTeams, parsePlayed, type GameRow } from './aggregateTeams'
import febTeams from '../../../tests/local_vectors/team_stats_feb.json'
import fbcylTeams from '../../../tests/local_vectors/team_stats_fbcyl.json'

// The last game of a team in the browser (issue #716, D4c): the figures of that game for the team and for its rival, from the rows of the contract (one per team and game, each with the
// rival's figures), as the weekly report's «Último partido» table reads them.
describe.each([['FEB', febTeams.rows], ['FBCYL', fbcylTeams.rows]] as const)('%s: the last game of each team', (_league, source) => {
  const rows = source as unknown as GameRow[]
  const names = [...new Set(rows.map(r => r.team_name))]

  it('is its most recent game by date, with its rival and the figures of both sides', () => {
    for (const name of names) {
      const mine = rows.filter(r => r.team_name === name && parsePlayed(r.starttime) !== null)
      const expected = mine.reduce((a, b) => (parsePlayed(b.starttime)! > parsePlayed(a.starttime)! ? b : a))
      const rival = rows.find(r => r.match_id === expected.match_id && r.team_id !== expected.team_id)
      const found = lastMatchOf(rows, name)
      expect(found, name).not.toBeNull()
      expect(found!.opponentName).toBe(rival?.team_name ?? '')
      const single = aggregateTeams([expected], {})
      expect(found!.team).toEqual(single.team_stats[0])
      expect(found!.opponent).toEqual(single.opponent_stats[0])
    }
  })

  it('has no last game for a team with no games or an unknown name', () => {
    expect(lastMatchOf(rows, 'No existe')).toBeNull()
    expect(lastMatchOf([], names[0])).toBeNull()
  })
})

describe('the date of the last game', () => {
  const base = (febTeams.rows as unknown as GameRow[])[0]
  const game = (over: Partial<GameRow>): GameRow => ({ ...base, ...over })

  it('is written day-month-year, and a game whose date cannot be read is never the last one', () => {
    const rows = [game({ match_id: 'a', team_id: 'T', team_name: 'T', starttime: '03-11-2025 - 18:30'.replace(' ', ' ') }), game({ match_id: 'b', team_id: 'T', team_name: 'T', starttime: 'not a date' }),
      game({ match_id: 'a', team_id: 'R', team_name: 'R', starttime: '03-11-2025 - 18:30' })]
    rows[0].starttime = '03-11-2025 - 18:30'
    const found = lastMatchOf(rows, 'T')
    expect(found?.date).toBe('03-11-2025')
    expect(found?.opponentName).toBe('R')
  })

  it('is an FBCYL day as FBCYL writes it', () => {
    const fbcyl = (fbcylTeams.rows as unknown as GameRow[])[0]
    const rows = [{ ...fbcyl, match_id: 'x', team_id: 'T', team_name: 'T', starttime: 'Oct 4, 2025 7:00:00 PM' }]
    expect(lastMatchOf(rows, 'T')?.date).toBe('04-10-2025')
    expect(lastMatchOf(rows, 'T')?.opponentName).toBe('')                      // the rival has no row of its own (a rival outside the competition)
  })
})
