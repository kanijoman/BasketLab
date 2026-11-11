import { describe, expect, it } from 'vitest'
import { buildGames, buildRatings, gamePace, gamesOf, matchupPace } from './gameLog'
import { TeamRatings } from './teamRatings'
import { fbcyl, lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'
import type { GameRow } from '@/localdata/aggregateTeams'
import type { Calendar, CalendarMatch } from '@/webdata/calendar'

// The games of a competition as the forecast reads them: the two rows of each match paired into one game (home, away, margin, pace), in the order they were played, plus the results the calendar has
// and the archive does not. Real competitions: a complete men's season, an early women's one with calendar results the rows lack, and an FBCYL group with a tied game.
describe('the games of a complete season (Primera FEB 2025-26)', () => {
  const { team_rows: rows } = primera()
  const games = buildGames(rows)

  it('has one game per match, with the local team at home and the margin from its side', () => {
    expect(games).toHaveLength(271)
    expect(new Set(games.map(g => g.id)).size).toBe(271)
    for (const g of games) {
      expect(g.homeRow!.is_local).toBe(true)
      expect(g.awayRow!.is_local).toBe(false)
      expect(g.margin).toBe(g.homeRow!.points - g.homeRow!.opponent_points)
      expect(g.margin).toBe(g.awayRow!.opponent_points - g.awayRow!.points)
      expect(String(g.home)).toBe(String(g.homeRow!.team_id))
    }
  })

  it('is in the order the games were played, whatever the order of the rows', () => {
    const shuffled = [...rows].sort((a, b) => (String(a.match_id) + a.team_id < String(b.match_id) + b.team_id ? 1 : -1))
    expect(buildGames(shuffled).map(g => g.id)).toEqual(games.map(g => g.id))
    const played = games.map(g => g.played)
    expect(played.every((t, i) => i === 0 || (t ?? Infinity) >= (played[i - 1] ?? Infinity))).toBe(true)
  })

  it('every game has a pace: the mean possessions of the two sides, per 40 minutes', () => {
    for (const g of games) expect(g.pace).toBeGreaterThan(40)
  })
})

describe('the awkward matches', () => {
  const { team_rows: rows } = primera()
  const first = String(rows[0].match_id)

  it('a match with only one row cannot be a game and is left out', () => {
    const one = rows.findIndex(r => String(r.match_id) === first)
    expect(buildGames(rows.filter((_, i) => i !== one))).toHaveLength(270)
  })

  it('a match whose rows do not say who is at home is left out', () => {
    const flat = rows.map(r => (String(r.match_id) === first ? { ...r, is_local: false } : r))
    expect(buildGames(flat)).toHaveLength(270)
  })

  it('a pace that the rows do not carry is estimated from the box score (FGA - ORB + TOV + 0.44 FTA)', () => {
    const row = rows[0]
    const bare: GameRow = { ...row, possessions: 0, opponent_possessions: 0 }
    const estimate = (r: GameRow, side: 'own' | 'opp') => {
      const p = side === 'own' ? '' : 'opponent_'
      const g = (k: string) => Number((r as unknown as Record<string, number>)[p + k])
      return g('fg2_attempts') + g('fg3_attempts') - g('off_rebounds') + g('turnovers') + 0.44 * g('ft_attempts')
    }
    expect(gamePace(bare)).toBeCloseTo((estimate(bare, 'own') + estimate(bare, 'opp')) / 2, 9)
    expect(gamePace(row)).toBeCloseTo((row.possessions + row.opponent_possessions) / 2, 9)
  })
})

describe('a game that ended tied (FBCYL)', () => {
  // the real group has no tied game yet: one real game with its score levelled (the shape the exporter gives a tie: `tied` on both rows and the same points)
  const rows = fbcyl().team_rows
  const first = String(rows[0].match_id)
  const levelled = rows.map(r => (String(r.match_id) === first ? { ...r, tied: true, won: false, points: 60, opponent_points: 60 } : r))
  const games = buildGames(levelled)

  it('is a tie with margin zero, and the rest are not', () => {
    const ties = games.filter(g => g.tied)
    expect(ties.map(g => g.id)).toEqual([first])
    expect(ties[0].margin).toBe(0)
    expect(games.filter(g => !g.tied).every(g => g.margin !== 0)).toBe(true)
  })

  it('FBCYL ids are numbers in the rows and texts in the game', () => {
    expect(typeof rows[0].team_id).toBe('number')
    expect(games.every(g => typeof g.home === 'string' && typeof g.away === 'string')).toBe(true)
  })
})

describe('the results of the calendar that the archive does not have', () => {
  const { team_rows: rows } = lfChallenge()
  const calendar = lfChallengeCalendar()
  const withCalendar = buildGames(rows, calendar)

  it('are added after the games of the rows, without rows and without a pace', () => {
    expect(buildGames(rows)).toHaveLength(39)
    expect(withCalendar).toHaveLength(47)
    const extra = withCalendar.slice(39)
    expect(extra.every(g => g.source === 'calendar' && !g.homeRow && g.pace === null && g.played === null)).toBe(true)
    expect(withCalendar.slice(0, 39).every(g => g.source === 'rows')).toBe(true)
  })

  it('take their margin from the score of the calendar, home first', () => {
    const calendarOnly = calendar.matches.filter(m => m.kind === 'result' && !rows.some(r => String(r.match_id) === m.match_id))
    expect(calendarOnly).toHaveLength(8)
    for (const m of calendarOnly) {
      const g = withCalendar.find(x => x.id === m.match_id)!
      expect([g.home, g.away]).toEqual([m.home.id, m.away.id])
      expect(g.margin).toBe(m.score![0] - m.score![1])
    }
  })

  it('a match being played (live) or still to play is not a result', () => {
    const live: CalendarMatch = { ...calendar.matches.find(m => m.kind === 'scheduled')!, kind: 'live', score: [10, 8] }
    const calendarWithLive: Calendar = { ...calendar, matches: [...calendar.matches, live] }
    expect(buildGames(rows, calendarWithLive)).toHaveLength(47)
  })

  it('a result that the rows have is not counted twice', () => {
    expect(withCalendar.filter(g => g.source === 'rows').length + withCalendar.filter(g => g.source === 'calendar').length).toBe(47)
    expect(new Set(withCalendar.map(g => g.id)).size).toBe(47)
  })
})

describe('the ratings and the pace of a matchup', () => {
  const games = buildGames(primera().team_rows)

  it('the ratings are the Kalman ones over the games in order', () => {
    const by = new TeamRatings()
    for (const g of games) by.update(g.home, g.away, g.margin)
    const ratings = buildRatings(games)
    for (const g of games.slice(0, 20)) expect(ratings.rating(g.home)).toBe(by.rating(g.home))
  })

  it('the pace of a matchup is the mean of the paces of the games of both teams, rounded to one decimal; none when neither has played', () => {
    const [a, b] = [games[0].home, games[0].away]
    const paces = [...gamesOf(games, a), ...gamesOf(games, b)].map(g => g.pace!)
    const want = Math.round((paces.reduce((s, x) => s + x, 0) / paces.length) * 10) / 10
    expect(matchupPace(games, a, b)).toBeCloseTo(want, 1)
    expect(matchupPace(games, 'nobody', 'nobody-else')).toBe(0)
  })

  it('gamesOf lists the games of a team, home or away, in order', () => {
    const team = games[0].home
    const mine = gamesOf(games, team)
    expect(mine.length).toBeGreaterThan(20)
    expect(mine.every(g => g.home === team || g.away === team)).toBe(true)
  })
})
