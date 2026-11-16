import { describe, expect, it } from 'vitest'
import { buildGames, gameMinutes } from '../gameLog'
import { buildModel, expectedOer, type ForecastModel } from '../pool'
import { boxOf, factors } from '../factors'
import type { Court } from '../winProb'
import { buildProjection } from './build'
import { MIN_MASS, project } from './project'
import { VARIABLES, type Condition, type VariableId } from './variables'
import { fbcyl, lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// The projection of a match (#936): every scenario of the pool, played by these two teams, is a whole game (possessions, the four factors and the points per 100 possessions of each side, the
// points, the margin), anchored so that the pool gives EXACTLY the headline. Asking for games where something happens (we score more than 70, the rival shoots under 40 %, more than 80
// possessions…) says how often it happens, how often we win in those games and what the REST of those games looks like. Conditional, never a promise. Real competitions: a complete men's
// season, an early women's one with calendar results the rows lack, and an FBCYL group (raw possessions and no minutes in its rows).
const complete = () => { const f = primera(); return buildModel(buildGames(f.team_rows), f.gender) }
const early = () => { const f = lfChallenge(); return buildModel(buildGames(f.team_rows, lfChallengeCalendar()), f.gender) }
const group = () => { const f = fbcyl(); return buildModel(buildGames(f.team_rows), f.gender) }

/** The strongest and the weakest team by rating, and a middling pair. */
function teamsBy(model: ForecastModel) {
  const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))].sort((a, b) => model.ratings.rating(b) - model.ratings.rating(a))
  return { best: ids[0], worst: ids[ids.length - 1], mid: [ids[Math.floor(ids.length / 2)], ids[Math.floor(ids.length / 2) + 1]] as const }
}

const COURTS: Court[] = ['own', 'rival', 'neutral']
const MIRROR: Record<Court, Court> = { own: 'rival', rival: 'own', neutral: 'neutral' }
const cond = (variable: VariableId, op: Condition['op'], value: number): Condition => ({ variable, op, value })

describe('the points of the pool', () => {
  it('every scenario, played by the two teams of its own game, gives back the points of each side of that game (overtime included)', () => {
    const model = complete()
    let i = 0
    for (const g of model.games) {
      if (!g.homeRow || !g.awayRow) continue
      for (const [o, r, ptsO, ptsR] of [[g.home, g.away, g.homePoints, g.awayPoints], [g.away, g.home, g.awayPoints, g.homePoints]] as const) {
        const s = model.pool[i++]
        expect(g.pace! * s.minutes * (expectedOer(model, o, r) + s.oOwn) / 100).toBeCloseTo(ptsO, 9)
        expect(g.pace! * s.minutes * (expectedOer(model, r, o) + s.oRiv) / 100).toBeCloseTo(ptsR, 9)
      }
    }
    expect(i).toBe(model.pool.length)
  })

  it('a game with overtime keeps its minutes (FEB: 40 plus 5 per overtime) and a row without them is a game of 40', () => {
    const model = complete()
    expect(model.pool.filter(s => s.minutes > 1).length).toBe(16)
    expect(model.pool.filter(s => s.minutes > 1).every(s => s.minutes === 45 / 40 || s.minutes === 50 / 40)).toBe(true)
    const games = buildGames(fbcyl().team_rows)
    expect(games.every(g => gameMinutes(g.homeRow!) === 1)).toBe(true)
  })

  it('is mirror symmetric in the points too: both sides of every game are in the pool', () => {
    const model = complete()
    const sum = (x: number[]) => x.reduce((a, b) => a + b, 0)
    expect(sum(model.pool.map(s => s.oOwn)) - sum(model.pool.map(s => s.oRiv))).toBeCloseTo(0, 6)
  })

  it('a team without rows scores what the league scores per 100 possessions', () => {
    const model = early()
    expect(expectedOer(model, 'nobody', 'nobody-else')).toBeCloseTo(model.oerLeague, 12)
  })
})

describe.each([['a complete men season', complete], ['an early women season with calendar results', early], ['an FBCYL group', group]] as const)('%s', (_name, make) => {
  const model = make()
  const { best, worst, mid } = teamsBy(model)
  const matchups = [[best, worst], [worst, best], [mid[0], mid[1]]] as const
  const cases = matchups.flatMap(([a, b]) => COURTS.map(c => [a, b, c] as const))

  it.each(cases)('with no condition it is the headline, and what those games look like is what is expected: %s vs %s on %s court', (own, rival, court) => {
    const p = buildProjection(model, own, rival, court)!
    expect(p.anchored).toBe(true)
    const r = project(p, [])
    expect(r.mass).toBeCloseTo(1, 12)
    expect(r.pWin).toBeCloseTo(p.headline.p, 6)
    expect(r.profile.map(x => x.variable)).toEqual(VARIABLES.map(v => v.id))
    for (const row of r.profile) {
      expect(Number.isFinite(row.expected)).toBe(true)
      expect(row.given).toBeCloseTo(row.expected, 9)
    }
  })

  it.each(cases)('a condition and its opposite share out the headline (total probability): %s vs %s on %s court', (own, rival, court) => {
    const p = buildProjection(model, own, rival, court)!
    const expected = (id: VariableId) => project(p, []).profile.find(x => x.variable === id)!.expected
    const pairs: [Condition, Condition][] = [
      [cond('own.points', 'gt', Math.round(expected('own.points'))), cond('own.points', 'lt', Math.round(expected('own.points')) + 1)],
      [cond('rival.points', 'gt', Math.round(expected('rival.points')) - 4), cond('rival.points', 'lt', Math.round(expected('rival.points')) - 3)],
      [cond('own.oer', 'gt', expected('own.oer') + 3), cond('own.oer', 'lt', expected('own.oer') + 3)],
      [cond('game.possessions', 'gt', expected('game.possessions') + 0.01), cond('game.possessions', 'lt', expected('game.possessions') + 0.01)],
      [cond('own.efg', 'gt', expected('own.efg')), cond('own.efg', 'lt', expected('own.efg'))],
      [cond('rival.tov', 'gt', expected('rival.tov')), cond('rival.tov', 'lt', expected('rival.tov'))],
    ]
    for (const [c, opposite] of pairs) {
      const [a, b] = [project(p, [c]), project(p, [opposite])]
      expect(a.mass + b.mass).toBeCloseTo(1, 9)
      expect(a.mass * a.pWin + b.mass * b.pWin).toBeCloseTo(p.headline.p, 6)
    }
  })

  it.each(matchups)('the points decide the result: if we score more than they can, we win; if less, we lose: %s vs %s', (own, rival) => {
    const p = buildProjection(model, own, rival, 'neutral')!
    const expected = (id: VariableId) => project(p, []).profile.find(x => x.variable === id)!.expected
    const t = Math.round((expected('own.points') + expected('rival.points')) / 2)          // a score both sides can reach
    expect(project(p, [cond('own.points', 'gt', t), cond('rival.points', 'lt', t)]).pWin).toBeCloseTo(1, 9)
    expect(project(p, [cond('own.points', 'lt', t), cond('rival.points', 'gt', t)]).pWin).toBeCloseTo(0, 9)
  })

  it.each(matchups.flatMap(([a, b]) => COURTS.map(c => [a, b, c] as const)))('swapping the teams mirrors it: our points for one are the rival points for the other: %s vs %s on %s court', (a, b, court) => {
    const [pa, pb] = [buildProjection(model, a, b, court)!, buildProjection(model, b, a, MIRROR[court])!]
    const [ra, rb] = [project(pa, [cond('own.points', 'gt', 70)]), project(pb, [cond('rival.points', 'gt', 70)])]
    expect(ra.mass).toBeCloseTo(rb.mass, 9)
    expect(ra.pWin + rb.pWin).toBeCloseTo(1, 6)
  })

  it.each(matchups)('combined conditions happen at most as often as the rarest of them: %s vs %s', (own, rival) => {
    const p = buildProjection(model, own, rival, 'own')!
    const c1 = cond('own.points', 'gt', 70)
    const c2 = cond('own.tov', 'lt', 0.18)
    const both = project(p, [c1, c2]).mass
    expect(both).toBeLessThanOrEqual(Math.min(project(p, [c1]).mass, project(p, [c2]).mass) + 1e-12)
  })

  it.each(matchups)('the points of more (or of less) split exactly into what the pace and what the efficiency give: %s vs %s', (own, rival) => {
    const p = buildProjection(model, own, rival, 'own')!
    for (const c of [cond('own.points', 'gt', 75), cond('game.possessions', 'gt', 76), cond('rival.efg', 'lt', 0.45)]) {
      const r = project(p, [c])
      for (const d of [r.points.own, r.points.rival]) expect(d.pace + d.efficiency).toBeCloseTo(d.given - d.expected, 9)
    }
  })

  it('the same question gives the same answer', () => {
    const p = buildProjection(model, best, worst, 'own')!
    const c = [cond('own.points', 'gt', 72), cond('rival.efg', 'lt', 0.48)]
    expect(project(p, c)).toEqual(project(buildProjection(model, best, worst, 'own')!, c))
  })
})

describe('a complete men season, in detail', () => {
  const model = complete()
  const { mid } = teamsBy(model)
  const p = buildProjection(model, mid[0], mid[1], 'own')!
  const base = project(p, [])
  const expected = (id: VariableId) => base.profile.find(x => x.variable === id)!.expected
  const given = (r: ReturnType<typeof project>, id: VariableId) => r.profile.find(x => x.variable === id)!.given

  it('a fast game has more possessions and more points for both sides', () => {
    const r = project(p, [cond('game.possessions', 'gt', expected('game.possessions') + 3)])
    expect(given(r, 'game.possessions')).toBeGreaterThan(expected('game.possessions') + 3)
    expect(given(r, 'own.points')).toBeGreaterThan(expected('own.points'))
    expect(given(r, 'rival.points')).toBeGreaterThan(expected('rival.points'))
    expect(r.points.own.pace).toBeGreaterThan(0)
  })

  it('scoring a lot comes with more possessions or more efficiency, and the win comes more often', () => {
    const r = project(p, [cond('own.points', 'gt', Math.round(expected('own.points')) + 8)])
    expect(given(r, 'own.points')).toBeGreaterThan(expected('own.points') + 8)
    expect(r.points.own.pace + r.points.own.efficiency).toBeGreaterThan(8)
    expect(r.pWin).toBeGreaterThan(p.headline.p)
  })

  it('a condition that almost never happens gives no figure (fewer than 5 of every 100 games like this)', () => {
    const r = project(p, [cond('own.points', 'gt', 125)])
    expect(r.mass).toBeLessThan(MIN_MASS)
    expect(r.rare).toBe(true)
    expect(r.figure).toBeNull()
  })

  it('a variable the evaluation does not back gives no figure, however often it happens; one it backs does', () => {
    const unbacked = VARIABLES.find(v => !v.supported)!
    const r = project(p, [cond(unbacked.id, 'gt', expected(unbacked.id))])
    expect(r.mass).toBeGreaterThan(MIN_MASS)
    expect(r.supported).toBe(false)
    expect(r.figure).toBeNull()
    const backed = VARIABLES.find(v => v.supported)!
    const s = project(p, [cond(backed.id, 'gt', expected(backed.id))])
    expect(s.supported).toBe(true)
    expect(s.figure).toBe(s.pWin)
  })

  // The walk-forward evaluation of 16/11/2026 (#938, 2,994 games of 14 seasons): ten variables are calibrated and beat the headline where their condition happens, in both families; the
  // possessions (as on 11/11, #857), our turnovers (calibrated, but no better than the headline) and the rival's points per 100 possessions (10 points off in the women's leagues) are not.
  const UNBACKED: VariableId[] = ['game.possessions', 'own.tov', 'rival.oer']
  it.each(VARIABLES.map(v => [v.id, !UNBACKED.includes(v.id)] as const))('%s: a figure only if the evaluation backs it (%s)', (id, backed) => {
    const r = project(p, [cond(id, 'gt', expected(id))])
    expect(r.rare).toBe(false)
    expect(r.figure === null).toBe(!backed)
  })

  it('the season record counts the games of ours that met every condition, and the ones we won (by hand)', () => {
    const own = mid[0]
    const conditions = [cond('own.points', 'gt', 80), cond('own.tov', 'lt', 0.16)]
    const mine = model.games.filter(g => g.homeRow && (g.home === own || g.away === own)).map(g => {
      const row = g.home === own ? g.homeRow! : g.awayRow!
      return { points: row.points, tov: factors(boxOf(row, 'own'), boxOf(row, 'opp')).tov, won: row.points > row.opponent_points }
    })
    const reached = mine.filter(m => m.points > 80 && m.tov < 0.16)
    expect(project(p, conditions).record).toEqual({ reached: reached.length, won: reached.filter(m => m.won).length })
  })
})

describe('without games', () => {
  it('there is nothing to project', () => {
    expect(buildProjection(buildModel([], 'F'), 'A', 'B', 'neutral')).toBeNull()
  })
})
