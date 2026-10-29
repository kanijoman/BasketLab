import { describe, expect, it } from 'vitest'
import { aggregateTeams, parsePlayed, type GameRow, type TeamTableFilter } from './aggregateTeams'
import vectors from '../../../tests/local_vectors/team_stats_fbcyl.json'

// FBCYL (issue #327): the same summing of the same row, with FBCYL's own table (fouls, wins and losses, total rebounds from its box, a tied game
// that is neither won nor lost, a date that is a day). Reference: `tests/local_vectors/generate.py` (the real FBCYL season pipeline).
type Row = Record<string, unknown>
const rows = vectors.rows as unknown as GameRow[]

describe('aggregateTeams with FBCYL rows (issue #327)', () => {
  it.each(vectors.cases.map(c => [c.name, c] as const))('%s: the team table equals the API', (_name, c) => {
    const got = aggregateTeams(rows, c.filter as TeamTableFilter).team_stats as unknown as Row[]
    const want = c.team_stats as unknown as Row[]
    expect(got.map(r => r.team_name).sort()).toEqual(want.map(r => r.team_name).sort())
    for (const expected of want) {
      const team = got.find(r => r.team_id === expected.team_id) as Row
      expect(team, `team ${String(expected.team_id)}`).toBeDefined()
      for (const [key, value] of Object.entries(expected)) {
        if (typeof value === 'number') expect(team[key] as number, key).toBeCloseTo(value, 9)
        else expect(team[key], key).toEqual(value)
      }
    }
  })

  it.each(vectors.cases.map(c => [c.name, c] as const))('%s: the rival table equals the API (it used to repeat the own table, #642)', (_name, c) => {
    const got = aggregateTeams(rows, c.filter as TeamTableFilter).opponent_stats as unknown as Row[]
    const want = c.opponent_stats as unknown as Row[]
    expect(got.map(r => r.team_name).sort()).toEqual(want.map(r => r.team_name).sort())
    for (const expected of want) {
      const team = got.find(r => r.team_id === expected.team_id) as Row
      expect(team, `team ${String(expected.team_id)}`).toBeDefined()
      for (const [key, value] of Object.entries(expected)) {
        if (typeof value === 'number') expect(team[key] as number, key).toBeCloseTo(value, 9)
        else expect(team[key], key).toEqual(value)
      }
    }
  })

  it.each(vectors.cases.map(c => [c.name, c] as const))('%s: the rival table is the real rival: what we receive is what they score', (_name, c) => {
    const { team_stats: own, opponent_stats: rival } = aggregateTeams(rows, c.filter as TeamTableFilter)
    for (const team of own) {
      const against = rival.find(r => r.team_id === team.team_id)!
      expect(against.total_games).toBe(team.total_games)
      expect(against.points_scored).toBe(team.points_received)             // what they do to us is what we receive
      expect(against.points_received).toBe(team.points_scored)
      expect(against.total_possessions).toBeCloseTo(team.opponent_possessions as number, 9)
      expect(against.total_rebounds).toBeDefined()
    }
    const sum = (t: typeof own, key: string) => t.reduce((n, r) => n + (r[key] as number), 0)
    expect(sum(rival, 'points_scored')).toBe(sum(own, 'points_received'))   // what all the rivals score is what all the teams receive, filtered or not
  })

  it('a tied game is neither won nor lost, and counts in the unfiltered table', () => {
    const lost = aggregateTeams(rows, { result: 'lost' }).team_stats.reduce((n, t) => n + t.total_games, 0)
    const won = aggregateTeams(rows, { result: 'won' }).team_stats.reduce((n, t) => n + t.total_games, 0)
    expect([won, lost, aggregateTeams(rows, {}).team_stats.reduce((n, t) => n + t.total_games, 0)]).toEqual([11, 11, 24])
  })

  it.each([
    ['Oct 4, 2025 7:00:00 PM', Date.UTC(2025, 9, 4)],
    ['Dec 31, 2025 12:00:00 AM', Date.UTC(2025, 11, 31)],
    ['05-10-2025 - 12:30', Date.UTC(2025, 9, 5, 12, 30)],
  ])('reads the date %s', (text, ms) => {
    expect(parsePlayed(text)).toBe(ms)
  })

  it.each(['', null, 'Foo 4, 2025 7:00:00 PM', '31-02-2025 - 10:00', 'Feb 30, 2025 1:00:00 PM'])('does not read %s', text => {
    expect(parsePlayed(text)).toBeNull()
  })
})
