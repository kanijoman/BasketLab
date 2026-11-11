import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel, type ForecastModel } from './pool'
import { evaluate } from './scenarios'
import { leversOf, quantile, type Lever } from './levers'
import { boxOf, factors, type FactorKey } from './factors'
import { lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// The objectives of the match, on the REAL games of the competition: for each thing a team can do (make or let make a factor of the game, and the pace) the target is where the 25 % of the
// scenarios of THIS matchup that go best in that direction begin; the objective says how often we win in those scenarios (against how often overall) and how the season went when we got there.
// It is conditional («when this happens, we win this often»), never a promise that making it happen wins.
const complete = () => {
  const f = primera()
  return buildModel(buildGames(f.team_rows), f.gender)
}
const early = () => {
  const f = lfChallenge()
  return buildModel(buildGames(f.team_rows, lfChallengeCalendar()), f.gender)
}

function teamsBy(model: ForecastModel) {
  const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))].sort((a, b) => model.ratings.rating(b) - model.ratings.rating(a))
  return { best: ids[0], worst: ids[ids.length - 1], mid: [ids[Math.floor(ids.length / 2)], ids[Math.floor(ids.length / 2) + 1]] as const }
}

const GOOD_UP: Record<FactorKey, boolean> = { efg: true, tov: false, orb: true, ftr: true }

describe.each([['a complete men season', complete], ['an early women season', early]] as const)('%s', (_name, make) => {
  const model = make()
  const { best, worst, mid } = teamsBy(model)
  const matchups = [[best, worst], [worst, best], [mid[0], mid[1]]] as const

  it.each(matchups)('every objective is where about a quarter of the scenarios begin, and each one is worth at least a point of probability: %s vs %s', (own, rival) => {
    const ev = evaluate(model, own, rival, 'own')!
    const { attack, defence, pace } = leversOf(model, ev)
    for (const l of [...attack, ...defence, ...(pace ? [pace] : [])]) {
      expect(l.mass).toBeGreaterThan(0.2)
      expect(l.mass).toBeLessThan(0.35)
      expect(l.gain).toBeGreaterThanOrEqual(0.01)
      expect(l.pWin).toBeCloseTo(ev.headline.p + l.gain, 12)
    }
  })

  it.each(matchups)('at most three of attack and three of defence, the most valuable first: %s vs %s', (own, rival) => {
    const ev = evaluate(model, own, rival, 'own')!
    const { attack, defence } = leversOf(model, ev)
    for (const list of [attack, defence]) {
      expect(list.length).toBeLessThanOrEqual(3)
      expect(list.map(l => l.gain)).toEqual([...list.map(l => l.gain)].sort((a, b) => b - a))
    }
    expect(attack.every(l => l.side === 'attack') && defence.every(l => l.side === 'defence')).toBe(true)
  })

  it.each(matchups)('the target is on the good side of what is expected, as each factor goes (more shooting, fewer turnovers of ours, fewer shots of theirs…): %s vs %s', (own, rival) => {
    const ev = evaluate(model, own, rival, 'own')!
    const { attack, defence } = leversOf(model, ev)
    for (const l of attack) {
      expect(l.direction).toBe(GOOD_UP[l.factor!] ? 'up' : 'down')
      expect(GOOD_UP[l.factor!] ? l.threshold > ev.expectedOwn[l.factor!] : l.threshold < ev.expectedOwn[l.factor!]).toBe(true)
    }
    for (const l of defence) {
      expect(l.direction).toBe(GOOD_UP[l.factor!] ? 'down' : 'up')            // what the rival makes: we want little of its good things and a lot of its turnovers
      expect(GOOD_UP[l.factor!] ? l.threshold < ev.expectedRival[l.factor!] : l.threshold > ev.expectedRival[l.factor!]).toBe(true)
    }
  })

  it('the pace that helps is the slow one for the team that is behind and the fast one for the favourite', () => {
    const under = leversOf(model, evaluate(model, worst, best, 'own')!).pace
    const over = leversOf(model, evaluate(model, best, worst, 'own')!).pace
    if (under) expect(under.direction).toBe('down')
    if (over) expect(over.direction).toBe('up')
  })

  it('is deterministic', () => {
    const ev = evaluate(model, mid[0], mid[1], 'neutral')!
    expect(leversOf(model, ev)).toEqual(leversOf(model, ev))
  })
})

describe('the season record of an objective, checked by hand on the real games', () => {
  const model = complete()
  const { mid } = teamsBy(model)
  const ev = evaluate(model, mid[0], mid[1], 'own')!
  const levers = leversOf(model, ev)
  const all: Lever[] = [...levers.attack, ...levers.defence]

  it('is how many games of the own team reached the target and how many of those it won', () => {
    expect(all.length).toBeGreaterThan(0)
    for (const l of all) {
      const mine = model.games.filter(g => (g.home === mid[0] || g.away === mid[0]) && g.homeRow)
      const reached = mine.filter(g => {
        const home = g.home === mid[0]
        const [o, r] = [boxOf(home ? g.homeRow! : g.awayRow!, 'own'), boxOf(home ? g.homeRow! : g.awayRow!, 'opp')]
        const value = l.side === 'attack' ? factors(o, r)[l.factor!] : factors(r, o)[l.factor!]
        return l.direction === 'up' ? value >= l.threshold : value <= l.threshold
      })
      const won = reached.filter(g => (g.home === mid[0] ? g.margin : -g.margin) > 0)
      expect(l.record).toEqual({ reached: reached.length, won: won.length })
    }
  })

  it('a team with no games has nothing to count: 0 of 0', () => {
    const ghost = evaluate(model, 'nobody', mid[1], 'own')!
    for (const l of [...leversOf(model, ghost).attack, ...leversOf(model, ghost).defence]) expect(l.record).toEqual({ reached: 0, won: 0 })
  })
})

describe('quantile', () => {
  it('is the linear one (NumPy default): the value at (n - 1) q between the sorted ones', () => {
    expect(quantile([1, 2, 3, 4], 0.75)).toBe(3.25)
    expect(quantile([1, 2, 3, 4], 0.25)).toBe(1.75)
    expect(quantile([5], 0.75)).toBe(5)
    expect(quantile([3, 1, 2], 0.5)).toBe(2)
  })
})
