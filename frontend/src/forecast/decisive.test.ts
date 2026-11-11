import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel } from './pool'
import { decisiveGames } from './decisive'
import { simulateSeason } from './seasonSim'
import { lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'

// The decisive games of a team: of the matches still to play, those whose result moves the position it is expected to finish in the most (the average position of the simulated seasons in which the
// home team wins against those in which it loses), and what each result does to the chance of a cut line. Real calendar (LF Challenge, 9/11/2026).
const f = lfChallenge()
const calendar = lfChallengeCalendar()
const model = buildModel(buildGames(f.team_rows, calendar), f.gender)
const sim = simulateSeason(model, calendar, { n: 4000, seed: 'decisive' })
const team = sim.table[3].team                                    // a team in the fight: fourth
const own = (d: { fixture: { home: string; away: string } }) => d.fixture.home === team || d.fixture.away === team

describe('the decisive games of a team', () => {
  const list = decisiveGames(sim, team)

  it('are the eight that move its position the most, the most first', () => {
    expect(list).toHaveLength(8)
    expect(list.map(d => d.swing)).toEqual([...list.map(d => d.swing)].sort((a, b) => b - a))
    expect(list.every(d => d.swing > 0)).toBe(true)
  })

  it('a game of the team itself is better for it when it wins: at home the home win is the better position, away the away win', () => {
    const mine = decisiveGames(sim, team, undefined, 200).filter(own)
    expect(mine.length).toBeGreaterThan(5)
    for (const d of mine) {
      if (d.fixture.home === team) expect(d.ifHomeWins.meanPosition).toBeLessThan(d.ifAwayWins.meanPosition)
      else expect(d.ifAwayWins.meanPosition).toBeLessThan(d.ifHomeWins.meanPosition)
    }
  })

  it('the games of the team weigh more than the rest of the league: the list has some, and they are marked', () => {
    expect(list.some(d => d.involvesTeam)).toBe(true)
    expect(list.every(d => d.involvesTeam === own(d))).toBe(true)
  })

  it('every game says how many seasons each result has, which cannot be more than all of them', () => {
    for (const d of decisiveGames(sim, team, undefined, 200)) expect(d.ifHomeWins.n + d.ifAwayWins.n).toBeLessThanOrEqual(sim.n)
  })

  it('with a cut line, what each result does to the chance of being inside it', () => {
    const top4 = decisiveGames(sim, team, { kind: 'top', n: 4 }, 200).filter(own)
    for (const d of top4) {
      const [win, lose] = d.fixture.home === team ? [d.ifHomeWins, d.ifAwayWins] : [d.ifAwayWins, d.ifHomeWins]
      expect(win.pCut!).toBeGreaterThanOrEqual(lose.pCut!)
    }
    expect(list[0].ifHomeWins.pCut).toBeNull()                                    // no cut line: no chance to tell
  })

  it('a team that is not in the league has none', () => {
    expect(decisiveGames(sim, 'nobody')).toEqual([])
  })

  it('a league with nothing left to play has none', () => {
    const over = simulateSeason(model, { ...calendar, matches: calendar.matches.filter(m => m.kind === 'result') }, { n: 50, seed: 'x' })
    expect(decisiveGames(over, team)).toEqual([])
  })
})
