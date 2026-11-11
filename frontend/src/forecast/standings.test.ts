import { describe, expect, it } from 'vitest'
import { buildGames, type GameResult } from './gameLog'
import { addResult, cloneLeague, newLeague, rankLeague, standingsOf } from './standings'
import { fbcyl, lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'

// The table of a league from its results, and the way ties are broken (a generic one, like the federation's but not recursive): wins, then the games among the tied teams (wins, then point
// difference), then the point difference of the whole league, then a seeded draw. Real results, and small leagues of two and three teams where each rule decides.
const game = (id: string, home: string, away: string, homePoints: number, awayPoints: number): GameResult => ({
  id, played: null, home, away, homeName: home, awayName: away, homePoints, awayPoints, margin: homePoints - awayPoints, tied: homePoints === awayPoints, pace: null, source: 'calendar',
})
const order = (games: GameResult[]) => standingsOf(games).map(r => r.team)

describe('the table of a real league (LF Challenge, 9/11/2026, with the results the calendar has)', () => {
  const f = lfChallenge()
  const games = buildGames(f.team_rows, lfChallengeCalendar())
  const table = standingsOf(games)

  it('has every team once, each with its games, and the games add up', () => {
    expect(table).toHaveLength(16)
    expect(new Set(table.map(r => r.team)).size).toBe(16)
    expect(table.reduce((s, r) => s + r.played, 0)).toBe(2 * games.length)
    for (const r of table) expect(r.won + r.lost + r.tied).toBe(r.played)
    expect(table.reduce((s, r) => s + r.won, 0)).toBe(games.length)
    expect(table.reduce((s, r) => s + r.pf, 0)).toBe(table.reduce((s, r) => s + r.pa, 0))
    expect(table.every(r => r.diff === r.pf - r.pa)).toBe(true)
  })

  it('is in order: most wins first, positions from 1, and the position is the place in the table', () => {
    expect(table.map(r => r.position)).toEqual(table.map((_, i) => i + 1))
    for (let i = 1; i < table.length; i++) expect(table[i - 1].won + table[i - 1].tied / 2).toBeGreaterThanOrEqual(table[i].won + table[i].tied / 2)
  })

  it('does not depend on the order of the games', () => {
    expect(order([...games].reverse())).toEqual(table.map(r => r.team))
  })

  it('gives the names of the teams', () => {
    expect(table.every(r => r.name.length > 0 && r.name !== r.team)).toBe(true)
  })
})

describe('a tied game of FBCYL is half a win for each', () => {
  const rows = fbcyl().team_rows
  const first = String(rows[0].match_id)
  const levelled = rows.map(r => (String(r.match_id) === first ? { ...r, tied: true, won: false, points: 60, opponent_points: 60 } : r))
  const games = buildGames(levelled)
  const table = standingsOf(games)

  it('counts it as tied for both and as no win and no loss', () => {
    const tie = games.find(g => g.tied)!
    for (const team of [tie.home, tie.away]) {
      const r = table.find(x => x.team === team)!
      expect(r.tied).toBe(1)
      expect(r.won + r.lost + r.tied).toBe(r.played)
    }
  })
})

describe('how ties are broken in a small league', () => {
  it('two teams with the same wins: the games between them decide (A won by 10 at home, B won by 4 at home: A is ahead by 6)', () => {
    expect(order([game('1', 'A', 'B', 80, 70), game('2', 'B', 'A', 74, 70)])).toEqual(['A', 'B'])
    expect(order([game('1', 'A', 'B', 80, 76), game('2', 'B', 'A', 80, 70)])).toEqual(['B', 'A'])
  })

  it('three teams in a cycle: the games among the three decide first, so the one that lost its win by most is last', () => {
    // A beat B by 5, B beat C by 7, C beat A by 3: one win each; among the three A +2, B +2, C -4
    const top = order([game('1', 'A', 'B', 75, 70), game('2', 'B', 'C', 77, 70), game('3', 'C', 'A', 73, 70)])
    expect(top[2]).toBe('C')
  })

  it('when the games among them cannot tell either, the point difference of the whole league does', () => {
    // A and B split their games with the same margin; A beat C by 30 and B beat C by 2
    const t = order([game('1', 'A', 'B', 75, 70), game('2', 'B', 'A', 75, 70), game('3', 'A', 'C', 100, 70), game('4', 'B', 'C', 72, 70), game('5', 'C', 'A', 90, 91), game('6', 'C', 'B', 70, 90)])
    expect(t.indexOf('A')).toBeLessThan(t.indexOf('B'))
  })

  it('when nothing tells them apart a draw decides, and the draw is the one it is given', () => {
    const state = newLeague(['A', 'B', 'C'])
    addResult(state, 0, 1, 5, false)
    addResult(state, 1, 2, 7, false)
    addResult(state, 2, 0, 3, false)                                       // A +5 -3, B -5 +7: the same among the three and in the league; C is last
    const first = rankLeague(state, [0.9, 0.1, 0.5])
    const second = rankLeague(state, [0.1, 0.9, 0.5])
    expect(first[1]).toBeLessThan(first[0])                                // B before A when B has the lower draw
    expect(second[0]).toBeLessThan(second[1])
    expect(first[2]).toBe(3)
  })

  it('a team with more wins is ahead whatever the rest says', () => {
    const t = order([game('1', 'A', 'B', 60, 90), game('2', 'B', 'C', 90, 60), game('3', 'A', 'C', 61, 60)])
    expect(t[0]).toBe('B')
  })
})

describe('the state of a league', () => {
  it('cloneLeague is independent of the original', () => {
    const a = newLeague(['A', 'B'])
    const b = cloneLeague(a)
    addResult(b, 0, 1, 10, false)
    expect(a.wins2[0]).toBe(0)
    expect(b.wins2[0]).toBe(2)
  })
})
