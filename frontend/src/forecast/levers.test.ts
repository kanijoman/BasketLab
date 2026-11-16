import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel, type ForecastModel } from './pool'
import { evaluate } from './scenarios'
import { bestPaceLever, leverCondition, leversOf, paceCandidates, quantile, type Lever } from './levers'
import { boxOf, factors, type FactorKey } from './factors'
import { buildProjection } from './projection/build'
import { project } from './projection/project'
import { variableOf } from './projection/variables'
import type { Court } from './winProb'
import { lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// The objectives of the match, on the REAL games of the competition: for each thing a team can do (make or let make a factor of the game, and the pace) the target is where the 25 % of the
// scenarios of THIS matchup that go best in that direction begin; the objective says how often we win in those games (against how often overall) and how the season went when we got there,
// and it is the answer of the projection of the match to that condition (#941): the card «¿Y si…?» gives the same figure for the same thing. It is conditional («when this happens, we win this
// often»), never a promise that making it happen wins. What the evaluation does not back (the pace, #857; our turnovers, 16/11/2026) is information, without a probability.
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

/** The evaluation and the projection of a matchup, which the objectives read. */
const matchupOf = (model: ForecastModel, own: string, rival: string, court: Court) => ({ ev: evaluate(model, own, rival, court)!, p: buildProjection(model, own, rival, court)! })

const GOOD_UP: Record<FactorKey, boolean> = { efg: true, tov: false, orb: true, ftr: true }

describe.each([['a complete men season', complete], ['an early women season', early]] as const)('%s', (_name, make) => {
  const model = make()
  const { best, worst, mid } = teamsBy(model)
  const matchups = [[best, worst], [worst, best], [mid[0], mid[1]]] as const

  it.each(matchups)('every objective is where about a quarter of the scenarios begin, and each one is worth at least a point of probability: %s vs %s', (own, rival) => {
    const { ev, p } = matchupOf(model, own, rival, 'own')
    const { attack, defence } = leversOf(p, ev)
    for (const l of [...attack, ...defence]) {
      expect(l.mass).toBeGreaterThan(0.2)
      expect(l.mass).toBeLessThan(0.35)
      expect(l.gain).toBeGreaterThanOrEqual(0.01)
      expect(l.pWin).toBeCloseTo(ev.headline.p + l.gain, 12)
    }
  })

  it.each(matchups)('one figure for one thing: the probability, the share and the season of an objective are what the projection says of the same condition: %s vs %s', (own, rival) => {
    const { ev, p } = matchupOf(model, own, rival, 'own')
    const { attack, defence } = leversOf(p, ev)
    expect(attack.length + defence.length).toBeGreaterThan(0)
    for (const l of [...attack, ...defence]) {
      const r = project(p, [leverCondition(l)])
      expect(l.pWin).toBe(r.pWin)
      expect(l.mass).toBe(r.mass)
      expect(l.record).toEqual({ reached: r.record.reached, won: r.record.won })
    }
  })

  it.each(matchups)('at most three of attack and three of defence, the most valuable first, and only of what the evaluation backs: %s vs %s', (own, rival) => {
    const { ev, p } = matchupOf(model, own, rival, 'own')
    const { attack, defence } = leversOf(p, ev)
    for (const list of [attack, defence]) {
      expect(list.length).toBeLessThanOrEqual(3)
      expect(list.map(l => l.gain)).toEqual([...list.map(l => l.gain)].sort((a, b) => b - a))
    }
    expect(attack.every(l => l.side === 'attack') && defence.every(l => l.side === 'defence')).toBe(true)
    for (const l of [...attack, ...defence]) expect(variableOf(l.variable).supported).toBe(true)
  })

  it.each(matchups)('the target is on the good side of what is expected, as each factor goes (more shooting, fewer turnovers of theirs for us…): %s vs %s', (own, rival) => {
    const { ev, p } = matchupOf(model, own, rival, 'own')
    const { attack, defence } = leversOf(p, ev)
    for (const l of attack) {
      expect(l.direction).toBe(GOOD_UP[l.factor!] ? 'up' : 'down')
      expect(GOOD_UP[l.factor!] ? l.threshold > ev.expectedOwn[l.factor!] : l.threshold < ev.expectedOwn[l.factor!]).toBe(true)
    }
    for (const l of defence) {
      expect(l.direction).toBe(GOOD_UP[l.factor!] ? 'down' : 'up')            // what the rival makes: we want little of its good things and a lot of its turnovers
      expect(GOOD_UP[l.factor!] ? l.threshold < ev.expectedRival[l.factor!] : l.threshold > ev.expectedRival[l.factor!]).toBe(true)
    }
  })

  it.each(matchups)('our turnovers are information, not an objective (16/11/2026: calibrated but no better than the headline): no «Cuidar el balón», and what is expected and the season at few and at many: %s vs %s', (own, rival) => {
    const { ev, p } = matchupOf(model, own, rival, 'own')
    const { attack, info } = leversOf(p, ev)
    expect(attack.some(l => l.factor === 'tov')).toBe(false)
    const tov = info.find(i => i.variable === 'own.tov')!
    expect(tov.expected).toBe(ev.expectedOwn.tov)
    expect(tov.low.threshold).toBeLessThan(tov.high.threshold)
    expect(Object.keys(tov).sort()).toEqual(['expected', 'high', 'low', 'variable'])
  })

  it('the pace that would help, if it were an objective, is the slow one for the team that is behind and the fast one for the favourite (the model, which the evaluation measures: #857)', () => {
    const [under, over] = [[worst, best], [best, worst]].map(([o, r]) => { const { ev, p } = matchupOf(model, o, r, 'own'); return bestPaceLever(paceCandidates(p, ev)) })
    if (under) expect(under.direction).toBe('down')
    if (over) expect(over.direction).toBe('up')
  })

  it('the pace is information, not an objective: the pace expected, a slow and a fast one and how the season went at each, and no probability of winning', () => {
    const { ev, p } = matchupOf(model, mid[0], mid[1], 'own')
    const [pace] = leversOf(p, ev).info
    expect(pace.variable).toBe('game.possessions')
    expect(Object.keys(pace).sort()).toEqual(['expected', 'high', 'low', 'variable'])
    expect(pace.expected).toBe(ev.headline.pace)
    expect(pace.low.threshold).toBeLessThan(pace.expected)
    expect(pace.high.threshold).toBeGreaterThan(pace.expected)
    for (const band of [pace.low, pace.high]) expect(Object.keys(band).sort()).toEqual(['record', 'threshold'])
  })

  it('is deterministic', () => {
    const { ev, p } = matchupOf(model, mid[0], mid[1], 'neutral')
    expect(leversOf(p, ev)).toEqual(leversOf(p, ev))
  })
})

describe('the season record of an objective, checked by hand on the real games', () => {
  const model = complete()
  const { mid } = teamsBy(model)
  const { ev, p } = matchupOf(model, mid[0], mid[1], 'own')
  const levers = leversOf(p, ev)
  const all: Lever[] = [...levers.attack, ...levers.defence]
  const mine = model.games.filter(g => (g.home === mid[0] || g.away === mid[0]) && g.homeRow && g.awayRow)
  const won = (g: (typeof mine)[number]) => (g.home === mid[0] ? g.margin : -g.margin) > 0

  it('is how many games of the own team went past the target and how many of those it won', () => {
    expect(all.length).toBeGreaterThan(0)
    for (const l of all) {
      const reached = mine.filter(g => {
        const home = g.home === mid[0]
        const [o, r] = [boxOf(home ? g.homeRow! : g.awayRow!, 'own'), boxOf(home ? g.homeRow! : g.awayRow!, 'opp')]
        const value = l.side === 'attack' ? factors(o, r)[l.factor!] : factors(r, o)[l.factor!]
        return l.direction === 'up' ? value > l.threshold : value < l.threshold
      })
      expect(l.record).toEqual({ reached: reached.length, won: reached.filter(won).length })
    }
  })

  it('the bands of the information count the own games at a slow or a fast pace, and with few or many turnovers, the same way', () => {
    const [pace, tov] = levers.info
    const turnovers = (g: (typeof mine)[number]) => { const row = g.home === mid[0] ? g.homeRow! : g.awayRow!; return factors(boxOf(row, 'own'), boxOf(row, 'opp')).tov }
    const cases = [[pace.low, (g: (typeof mine)[number]) => g.pace! < pace.low.threshold], [pace.high, (g: (typeof mine)[number]) => g.pace! > pace.high.threshold],
      [tov.low, (g: (typeof mine)[number]) => turnovers(g) < tov.low.threshold], [tov.high, (g: (typeof mine)[number]) => turnovers(g) > tov.high.threshold]] as const
    for (const [band, past] of cases) {
      const reached = mine.filter(past)
      expect(band.record).toEqual({ reached: reached.length, won: reached.filter(won).length })
    }
  })

  it('a team with no games has nothing to count: 0 of 0', () => {
    const ghost = matchupOf(model, 'nobody', mid[1], 'own')
    for (const l of [...leversOf(ghost.p, ghost.ev).attack, ...leversOf(ghost.p, ghost.ev).defence]) expect(l.record).toEqual({ reached: 0, won: 0 })
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
