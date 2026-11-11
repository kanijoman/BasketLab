import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel } from './pool'
import { gameSpread, pBottom, pTop, simulateSeason, SIMULATIONS } from './seasonSim'
import { standingsOf } from './standings'
import { lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'
import type { Calendar } from '@/webdata/calendar'

// The simulation of the league on a REAL calendar (LF Challenge on 9/11/2026: 16 teams, 47 results of which 8 are not in the archive, 193 matches still to play): the strength of each team is drawn
// once per season from what the Kalman rating knows of it, each remaining match is played from those strengths and the home court of the family, and the table is ranked with the generic tie-break.
const f = lfChallenge()
const calendar = lfChallengeCalendar()
const model = buildModel(buildGames(f.team_rows, calendar), f.gender)
const N = 2000
const sim = simulateSeason(model, calendar, { n: N, seed: 'test' })
const T = sim.teams.length

describe('the simulated seasons', () => {
  it('know what is left to play and who is in the league', () => {
    expect(T).toBe(16)
    expect(sim.remaining).toHaveLength(193)
    expect(sim.n).toBe(N)
    expect(sim.table).toEqual(standingsOf(model.games))
  })

  it('give every team one position in every season: each team adds up to all the seasons, and so does each position', () => {
    for (let t = 0; t < T; t++) expect(sim.positionCounts[t].reduce((a, b) => a + b, 0)).toBe(N)
    for (let pos = 0; pos < T; pos++) expect(sim.positionCounts.reduce((s, row) => s + row[pos], 0)).toBe(N)
  })

  it('give one winner to every game: the expected wins of the league are the games played plus those left', () => {
    expect(sim.expectedWins.reduce((a, b) => a + b, 0)).toBeCloseTo(model.games.length + sim.remaining.length, 9)
    sim.table.forEach(r => expect(sim.expectedWins[sim.teams.indexOf(r.team)]).toBeGreaterThanOrEqual(r.won))
  })

  it('give a first place to exactly one team per season', () => {
    expect(sim.pFirst.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 12)
    expect(sim.pFirst.every(p => p >= 0 && p <= 1)).toBe(true)
  })

  it('favour the stronger teams: the best team by rating averages a better position than the worst', () => {
    const byRating = [...sim.teams].sort((a, b) => model.ratings.rating(b) - model.ratings.rating(a))
    const mean = (team: string) => sim.meanPosition[sim.teams.indexOf(team)]
    expect(mean(byRating[0])).toBeLessThan(mean(byRating[T - 1]))
    expect(mean(byRating[0])).toBeLessThan(T / 2)
  })

  it('are the same for the same seed and different for another', () => {
    const again = simulateSeason(model, calendar, { n: 500, seed: 'a' })
    expect(simulateSeason(model, calendar, { n: 500, seed: 'a' }).positionCounts).toEqual(again.positionCounts)
    expect(simulateSeason(model, calendar, { n: 500, seed: 'b' }).positionCounts).not.toEqual(again.positionCounts)
  })

  it('by default are those of 10,000 seasons seeded with the name of the competition, so a reload shows the same numbers', () => {
    expect(SIMULATIONS).toBe(10000)
    const a = simulateSeason(model, calendar, { n: 300 })
    expect(simulateSeason(model, calendar, { n: 300 }).meanPosition).toEqual(a.meanPosition)
  })
})

describe('what a simulated game is', () => {
  it('has the spread of a game of the family minus what the two ratings are unsure of, never under 12 points', () => {
    expect(gameSpread(14, 10, 10)).toBeCloseTo(Math.sqrt(176), 12)
    expect(gameSpread(14, 40, 40)).toBe(12)                                          // the floor: 196 - 80 = 116 < 144
    expect(gameSpread(15, 0, 0)).toBe(15)
  })

  it('has one outcome per match and season: the home team wins or the away team does, and a tie only where the group allows it', () => {
    expect(sim.outcomes).toHaveLength(N * 193)
    expect(new Set(sim.outcomes)).toEqual(new Set([0, 1]))
    const allowed = simulateSeason(model, { ...calendar, ties_allowed: true }, { n: 1000, seed: 'ties' })
    expect(allowed.outcomes.includes(2)).toBe(true)
    expect(allowed.expectedWins.reduce((a, b) => a + b, 0)).toBeCloseTo(model.games.length + 193, 9)      // a tie is half a win for each: the league total does not change
  })

  it('has more wins for the home team than for the away one (the home court)', () => {
    let home = 0
    for (const o of sim.outcomes) home += o
    expect(home / sim.outcomes.length).toBeGreaterThan(0.5)
  })
})

describe('the matches that are not like the rest', () => {
  it('a match being played (live) is still to play', () => {
    const live: Calendar = { ...calendar, matches: calendar.matches.map(m => (m.code === calendar.matches.find(x => x.kind === 'scheduled')!.code ? { ...m, kind: 'live' as const } : m)) }
    expect(simulateSeason(model, live, { n: 50, seed: 'x' }).remaining).toHaveLength(193)
  })

  it('a match that the games already have is not played twice', () => {
    const played = model.games[0].id
    const first = calendar.matches.findIndex(m => m.kind === 'scheduled')
    const odd: Calendar = { ...calendar, matches: calendar.matches.map((m, i) => (i === first ? { ...m, match_id: played } : m)) }
    expect(simulateSeason(model, odd, { n: 50, seed: 'x' }).remaining).toHaveLength(192)
  })

  it('a season that is over is its table, whatever the seed: every team has its position in every season', () => {
    const over: Calendar = { ...calendar, matches: calendar.matches.filter(m => m.kind === 'result') }
    const done = simulateSeason(model, over, { n: 100, seed: 'x' })
    expect(done.remaining).toEqual([])
    for (const row of done.table) {
      const t = done.teams.indexOf(row.team)
      expect(done.positionCounts[t][row.position - 1]).toBe(100)
      expect(done.expectedWins[t]).toBe(row.won + row.tied / 2)
    }
  })

  it('a team of the calendar that has no game yet is in the league with the rating of a team never seen', () => {
    const extra: Calendar = { ...calendar, matches: [...calendar.matches, { ...calendar.matches.find(m => m.kind === 'scheduled')!, code: 'x1', match_id: 'x1', home: { id: 'NEW', name: 'RECIÉN LLEGADO' } }] }
    const s = simulateSeason(model, extra, { n: 200, seed: 'x' })
    expect(s.teams).toContain('NEW')
    expect(s.names.NEW).toBe('RECIÉN LLEGADO')
  })
})

describe('the cut lines', () => {
  it('the chance of being in the first n is the sum of the first n positions, and the last n the sum of the last n', () => {
    const t = 0
    expect(pTop(sim, t, 1)).toBe(sim.pFirst[t])
    expect(pTop(sim, t, T)).toBe(1)
    expect(pTop(sim, t, 4)).toBeCloseTo(sim.positionCounts[t].slice(0, 4).reduce((a, b) => a + b, 0) / N, 12)
    expect(pBottom(sim, t, 2)).toBeCloseTo(sim.positionCounts[t].slice(T - 2).reduce((a, b) => a + b, 0) / N, 12)
    expect(pTop(sim, t, 0)).toBe(0)
  })
})

describe('the cost', () => {
  it('10,000 seasons of the real calendar take a few seconds at most', () => {
    const started = performance.now()
    simulateSeason(model, calendar, { n: SIMULATIONS, seed: 'speed' })
    expect(performance.now() - started).toBeLessThan(8000)
  })
})
