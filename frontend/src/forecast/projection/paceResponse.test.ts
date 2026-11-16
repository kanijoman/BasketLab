import { describe, expect, it } from 'vitest'
import { buildGames } from '../gameLog'
import { buildModel, type ForecastModel } from '../pool'
import { buildProjection } from './build'
import { paceResponse, RESPONSE_KEYS, type ResponseKey } from './paceResponse'
import { project } from './project'
import { lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// The layer of each team (#937): the pool mixes the games of every team, so how the factors and the points per 100 possessions move with the pace is the league's. Here each team has its own
// slope against the pace of the game (what it makes, attack, and what it lets make, defence), shrunk towards the league's by games / (games + k), and every scenario played by two teams moves by
// what those two slopes say beyond the league's at that scenario's pace. Optional: the evaluation decides whether it goes to the page.
const complete = () => { const f = primera(); return buildModel(buildGames(f.team_rows), f.gender) }
const early = () => { const f = lfChallenge(); return buildModel(buildGames(f.team_rows, lfChallengeCalendar()), f.gender) }

const teamsOf = (model: ForecastModel): string[] => [...new Set(model.pool.map(s => s.own))].sort()

/** The slope of y on x (least squares with intercept). */
function slope(xs: number[], ys: number[]): number {
  const mx = xs.reduce((a, b) => a + b, 0) / xs.length
  const my = ys.reduce((a, b) => a + b, 0) / ys.length
  const sxx = xs.reduce((s, x) => s + (x - mx) ** 2, 0)
  return sxx > 0 ? xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0) / sxx : 0
}
const residual = (key: ResponseKey, side: 'own' | 'rival') => (s: ForecastModel['pool'][number]) =>
  key === 'oer' ? (side === 'own' ? s.oOwn : s.oRiv) : (side === 'own' ? s.dOwn : s.dRiv)[key]

describe.each([['a complete men season', complete], ['an early women season', early]] as const)('%s', (_name, make) => {
  const model = make()
  const teams = teamsOf(model)

  it('every scenario says whose it is: the own and the rival team of its game', () => {
    for (const s of model.pool) expect(teams).toContain(s.own)
    expect(model.pool.every(s => s.own !== s.rival)).toBe(true)
  })

  it('the slope of a team is the regression of its residuals on the pace of its games (by hand), and the league one is that of every side', () => {
    const r = paceResponse(model)
    for (const key of RESPONSE_KEYS) {
      expect(r.league[key]).toBeCloseTo(slope(model.pool.map(s => s.rho - 1), model.pool.map(residual(key, 'own'))), 12)
      for (const team of teams.slice(0, 4)) {
        const mine = model.pool.filter(s => s.own === team)
        expect(r.raw(team).attack[key]).toBeCloseTo(slope(mine.map(s => s.rho - 1), mine.map(residual(key, 'own'))), 12)
        expect(r.raw(team).defence[key]).toBeCloseTo(slope(mine.map(s => s.rho - 1), mine.map(residual(key, 'rival'))), 12)
      }
    }
  })

  it('the slope used is between the team one and the league one, nearer the team the more games it has', () => {
    const r = paceResponse(model, 10)
    for (const team of teams) for (const side of ['attack', 'defence'] as const) for (const key of RESPONSE_KEYS) {
      const [raw, used, league] = [r.raw(team)[side][key], r.level(team)[side][key], r.league[key]]
      expect(used).toBeGreaterThanOrEqual(Math.min(raw, league) - 1e-12)
      expect(used).toBeLessThanOrEqual(Math.max(raw, league) + 1e-12)
      const n = model.pool.filter(s => s.own === team).length
      expect(used - league).toBeCloseTo((raw - league) * (n / (n + 10)), 12)
    }
  })

  it('a team never seen has the league slope', () => {
    const r = paceResponse(model)
    for (const side of ['attack', 'defence'] as const) expect(r.level('nobody')[side]).toEqual(r.league)
  })

  it('with an infinite shrinkage every team is the league and the projection is the one of the league layer', () => {
    const [a, b] = [teams[0], teams[1]]
    const plain = buildProjection(model, a, b, 'own')!
    const layered = buildProjection(model, a, b, 'own', { paceResponse: paceResponse(model, 1e15) })!
    plain.ownPoints.forEach((x, i) => expect(layered.ownPoints[i]).toBeCloseTo(x, 6))
    plain.fOwn.forEach((f, i) => expect(layered.fOwn[i].tov).toBeCloseTo(f.tov, 9))
  })

  it.each([['own'], ['rival'], ['neutral']] as const)('with the layer the projection is still anchored to the headline (%s court)', court => {
    const [a, b] = [teams[0], teams[teams.length - 1]]
    const p = buildProjection(model, a, b, court, { paceResponse: paceResponse(model) })!
    expect(p.anchored).toBe(true)
    expect(project(p, []).pWin).toBeCloseTo(p.headline.p, 6)
  })
})

describe('a complete men season, the team whose turnovers go up the most with the pace', () => {
  const model = complete()
  const r = paceResponse(model)
  const team = teamsOf(model).sort((x, y) => r.level(y).attack.tov - r.level(x).attack.tov)[0]
  const rival = teamsOf(model).find(t => t !== team)!

  it('in the fast games it is projected to lose more balls with the layer than with the league alone', () => {
    expect(r.level(team).attack.tov).toBeGreaterThan(r.league.tov)
    const fast = [{ variable: 'game.possessions' as const, op: 'gt' as const, value: 76 }]
    const tov = (q: ReturnType<typeof project>) => q.profile.find(x => x.variable === 'own.tov')!.given
    const plain = project(buildProjection(model, team, rival, 'own')!, fast)
    const layered = project(buildProjection(model, team, rival, 'own', { paceResponse: r })!, fast)
    expect(tov(layered)).toBeGreaterThan(tov(plain))
  })
})
