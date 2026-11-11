import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { nextFixture, teamFixtures } from './fixtures'
import { lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'
import type { Calendar } from '@/webdata/calendar'

// The matches a team has left, from the real calendar (LF Challenge, 9/11/2026: 16 teams, 193 matches to play, 8 results the archive lacks): what the page lists after choosing a team, with the rival
// and where it is played.
const f = lfChallenge()
const calendar = lfChallengeCalendar()
const games = buildGames(f.team_rows, calendar)
const team = games[0].home

describe('the fixtures of a team', () => {
  const list = teamFixtures(games, calendar, team)

  it('are the matches still to play in which it plays, all of them, and nobody else\'s', () => {
    const mine = calendar.matches.filter(m => (m.kind === 'scheduled' || m.kind === 'live') && (m.home.id === team || m.away.id === team))
    expect(list.map(x => x.code).sort()).toEqual(mine.map(m => m.code).sort())
    const played = games.filter(g => g.home === team || g.away === team).length
    expect(list.length + played).toBe(30)                                  // 16 teams, each plays the other 15 twice
  })

  it('say who the rival is and where it is played, from the side of the team', () => {
    for (const x of list) {
      const m = calendar.matches.find(c => c.code === x.code)!
      if (m.home.id === team) expect([x.court, x.rival, x.rivalName]).toEqual(['own', m.away.id, m.away.name])
      else expect([x.court, x.rival, x.rivalName]).toEqual(['rival', m.home.id, m.home.name])
    }
  })

  it('are in the order they will be played: by kick-off, those without one at the end', () => {
    const starts = list.map(x => x.start)
    expect(starts.every((s, i) => i === 0 || (s ?? '9999') >= (starts[i - 1] ?? '9999'))).toBe(true)
  })

  it('do not include a match that is already played, even if the calendar still lists it as to play', () => {
    const played = games.find(g => g.home === team || g.away === team)!
    const odd: Calendar = { ...calendar, matches: calendar.matches.map(m => (m.code === list[0].code ? { ...m, match_id: played.id } : m)) }
    expect(teamFixtures(games, odd, team).map(x => x.code)).not.toContain(list[0].code)
  })

  it('a team without matches left, or one that is not in the calendar, has none', () => {
    expect(teamFixtures(games, { ...calendar, matches: calendar.matches.filter(m => m.kind === 'result') }, team)).toEqual([])
    expect(teamFixtures(games, calendar, 'nobody')).toEqual([])
  })
})

describe('the next fixture', () => {
  const list = teamFixtures(games, calendar, team)
  const at = (iso: string) => Date.parse(`${iso}:00Z`)

  it('is the first that has not started (a match that began less than three hours ago still counts)', () => {
    const [first, second] = list
    expect(nextFixture(list, at(first.start!) - 60 * 60_000)!.code).toBe(first.code)
    expect(nextFixture(list, at(first.start!) + 2 * 60 * 60_000)!.code).toBe(first.code)
    expect(nextFixture(list, at(first.start!) + 4 * 60 * 60_000)!.code).toBe(second.code)
  })

  it('is the last one when all are in the past, and nothing when there are none', () => {
    expect(nextFixture(list, at('2030-01-01T00:00'))!.code).toBe(list[list.length - 1].code)
    expect(nextFixture([], 0)).toBeNull()
  })
})
