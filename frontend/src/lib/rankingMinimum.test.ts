import { describe, expect, it } from 'vitest'
import type { PlayerStat } from '@/api/client'
import { MEDIAN_MIN_GAMES, SHARE_OF_MEDIAN, VOLUME, minimumFor, teamGamesOf } from './rankingMinimum'

// Issue #763: a ranking of a rate (a percentage, a rating, a «per game» average) is falsified by whoever has almost no volume behind it (a 100 % on two attempts).
// The minimum is the SAME rule for every statistic, relative to the competition: at least half of the median volume per game of the team, where the volume is what the
// statistic is made of (attempts of its category, or minutes for the rates of the court and the averages per game).
const player = (id: string, team: string, games: number, extra: Partial<PlayerStat> = {}): PlayerStat =>
  ({ player_id: id, player_name: id, team_name: team, team_id: team, games_played: games, total_minutes: games * 20, minutes_per_game: 20, ...extra } as PlayerStat)

describe('the rule', () => {
  it('is half of the median, over players with at least three games', () => {
    expect(SHARE_OF_MEDIAN).toBe(0.5)
    expect(MEDIAN_MIN_GAMES).toBe(3)
  })
})

describe('teamGamesOf', () => {
  it('a team has played as many games as its player who played the most', () => {
    const games = teamGamesOf([player('a', 'X', 10), player('b', 'X', 7), player('c', 'Y', 4)])
    expect([games.get('X'), games.get('Y')]).toEqual([10, 4])
  })

  it('a player without team id is told by the name of his team', () => {
    const games = teamGamesOf([{ ...player('a', 'X', 6), team_id: undefined }, { ...player('b', 'X', 3), team_id: undefined }])
    expect(games.get('X')).toBe(6)
  })
})

describe('minimumFor attempts', () => {
  // ten games per team; attempts of 2 points per game: 4, 3, 2, 1, 0 → the median is 2 per game, the minimum 1 per game = 10 attempts
  const ps = [40, 30, 20, 10, 0].map((p2a, i) => player(`p${i}`, 'X', 10, { total_p2a: p2a }))

  it('half of the median per game of the team, as total attempts', () => {
    const minimum = minimumFor(ps, 'p2a')
    expect(minimum.perTeamGame).toBe(1)
    expect(ps.filter(p => minimum.qualifies(p)).map(p => p.player_id)).toEqual(['p0', 'p1', 'p2', 'p3'])         // the boundary (10 attempts) is in, the player who never shot is out
  })

  it('the players who never shot count in the median: a category few players use asks little', () => {
    const rarely = [20, 0, 0, 0, 0].map((p3a, i) => player(`q${i}`, 'X', 10, { total_p3a: p3a }))
    expect(minimumFor(rarely, 'p3a').perTeamGame).toBe(0)                    // the median is zero: nobody is left out for shooting few threes
    expect(rarely.every(p => minimumFor(rarely, 'p3a').qualifies(p))).toBe(true)
  })

  it('players with fewer than three games do not make the median but are judged by it', () => {
    const base = [40, 30, 20].map((p2a, i) => player(`p${i}`, 'X', 10, { total_p2a: p2a }))
    const rookie = player('rookie', 'X', 2, { total_p2a: 400 })              // would move the median if counted
    const minimum = minimumFor([...base, rookie], 'p2a')
    expect(minimum.perTeamGame).toBe(1.5)                                    // median of 4, 3, 2 is 3 → half is 1.5 per game
    expect(minimum.qualifies(rookie)).toBe(true)
    expect(minimum.qualifies(player('cameo', 'X', 2, { total_p2a: 2 }))).toBe(false)     // 2 attempts of the 15 that ten team games ask for
  })

  it('is asked per game of the team: a team that has played more games asks for more attempts', () => {
    const a = [30, 30, 30].map((p2a, i) => player(`a${i}`, 'A', 10, { total_p2a: p2a }))
    const b = [12, 12, 12].map((p2a, i) => player(`b${i}`, 'B', 4, { total_p2a: p2a }))
    const minimum = minimumFor([...a, ...b], 'p2a')                          // per team game: 3, 3, 3, 3, 3, 3 → minimum 1.5 per game
    expect(minimum.qualifies(player('x', 'A', 10, { total_p2a: 14 }))).toBe(false)       // 14 < 15
    expect(minimum.qualifies(player('y', 'B', 4, { total_p2a: 6 }))).toBe(true)          // 6 = 1.5 × 4
    expect(minimum.qualifies(player('z', 'B', 4, { total_p2a: 5 }))).toBe(false)
  })

  it('the first games of a season already have a minimum (four games of the team: four attempts of two)', () => {
    const ps4 = [8, 8, 8].map((p2a, i) => player(`e${i}`, 'X', 4, { total_p2a: p2a }))       // 2 per game → minimum 1 per game
    expect(minimumFor(ps4, 'p2a').qualifies(player('few', 'X', 4, { total_p2a: 3 }))).toBe(false)
    expect(minimumFor(ps4, 'p2a').qualifies(player('some', 'X', 4, { total_p2a: 4 }))).toBe(true)
  })

  it('without data (no totals, no players) nobody is left out', () => {
    const noTotals = [player('a', 'X', 10), player('b', 'X', 10)]
    expect(minimumFor(noTotals, 'p2a').perTeamGame).toBe(0)
    expect(noTotals.every(p => minimumFor(noTotals, 'p2a').qualifies(p))).toBe(true)
    expect(minimumFor([], 'p2a').perTeamGame).toBe(0)
  })
})

describe('what a statistic is made of', () => {
  const p = player('a', 'X', 10, { total_p1a: 10, total_p2a: 20, total_p3a: 5, total_minutes: 250 })

  it('attempts of the category, the field goals, and the shots that count for the true shooting', () => {
    expect([VOLUME.p1a.of(p), VOLUME.p2a.of(p), VOLUME.p3a.of(p), VOLUME.fga.of(p)]).toEqual([10, 20, 5, 25])
    expect(VOLUME.tsa.of(p)).toBeCloseTo(25 + 0.44 * 10, 9)
  })

  it('minutes: the total, or the average per game times the games when only that is there', () => {
    expect(VOLUME.minutes.of(p)).toBe(250)
    expect(VOLUME.minutes.of({ ...p, total_minutes: undefined as unknown as number, minutes_per_game: 18.5, games_played: 5 })).toBe(92.5)
  })

  it('the unit says what the minimum counts', () => {
    expect(VOLUME.p3a.unit).toBe('intentos de triple')
    expect(VOLUME.minutes.unit).toBe('minutos')
  })
})
