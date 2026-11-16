import { describe, expect, it } from 'vitest'
import { buildGames, type GameResult } from '../gameLog'
import { buildModel } from '../pool'
import { gameValue, meets, VARIABLES } from '../projection/variables'
import { RESPONSE_KEYS } from '../projection/paceResponse'
import { leaguePaceSlopes, pearson, rivalResponse, splitHalf, walkForwardProjection } from './projection'
import { formatProjectionSection } from './projectionReport'
import { primera } from '@/test/forecastFixtures'

// The evaluation of the projection of a match (#938) on a REAL season (Primera FEB 2025-26, the first 150 games here so it is quick). Every projection is made with the games BEFORE the one it is
// judged on: what is checked is that, in the games where a condition happened, the probability it gave matches how often the team won, and that knowing one variable of the game (its pace, the
// points of one side) the projection foresees the others better than without it.
const all = buildGames(primera().team_rows)
const games = all.slice(0, 150)
const flippedAfter = (index: number): GameResult[] => games.map((g, i) => (i > index ? { ...g, margin: -g.margin, homePoints: g.awayPoints, awayPoints: g.homePoints } : g))
const OPTIONS = { from: 100, every: 10, ks: [10, 40] }

describe('the walk-forward of the projection', () => {
  const study = walkForwardProjection(games, 'M', OPTIONS)

  it('judges every condition against the game that was played, from the side of both teams', () => {
    expect(study.conditions.length).toBeGreaterThan(0)
    for (const r of study.conditions) {
      const g = games[r.k]
      const team = r.court === 'own' ? g.home : g.away
      expect(r.met).toBe(r.conditions.every(c => meets(gameValue(g, team, c.variable)!, c)))
      expect(r.y).toBe((r.court === 'own' ? g.margin : -g.margin) > 0 ? 1 : 0)
      expect(r.mass).toBeGreaterThan(0)
      expect(r.mass).toBeLessThanOrEqual(1)
      expect(r.pWin).toBeGreaterThanOrEqual(0)
      expect(r.pWin).toBeLessThanOrEqual(1)
    }
    expect(new Set(study.conditions.map(r => r.court))).toEqual(new Set(['own', 'rival']))
  })

  it('asks of every variable, in both directions, alone and two at a time, with the league layer and with the layer of each team', () => {
    const singles = study.conditions.filter(r => r.conditions.length === 1)
    expect(new Set(singles.map(r => r.conditions[0].variable))).toEqual(new Set(VARIABLES.map(v => v.id)))
    expect(new Set(singles.map(r => r.conditions[0].op))).toEqual(new Set(['gt', 'lt']))
    expect(study.conditions.some(r => r.conditions.length === 2)).toBe(true)
    expect(new Set(study.conditions.map(r => r.layer))).toEqual(new Set(['liga', 'equipo']))
  })

  it('foresees the variables of the game knowing one of them, against what was expected without it, and with each layer', () => {
    const layers = new Set(study.predictions.map(r => r.layer))
    expect(layers).toEqual(new Set(['ninguna', 'liga', 'equipo k=10', 'equipo k=40']))
    for (const r of study.predictions) {
      const g = games[r.k]
      expect(r.target).not.toBe(r.given)
      expect(r.actual).toBe(gameValue(g, r.court === 'own' ? g.home : g.away, r.target))
      expect(Number.isFinite(r.predicted)).toBe(true)
    }
  })

  it('does not leak: turning round every result after a game does not change what was projected up to it', () => {
    const other = walkForwardProjection(flippedAfter(120), 'M', OPTIONS)
    const upTo = (s: typeof study) => ({ c: s.conditions.filter(r => r.k <= 120).map(r => [r.k, r.mass, r.pWin]), p: s.predictions.filter(r => r.k <= 120).map(r => [r.k, r.predicted]) })
    expect(upTo(other)).toEqual(upTo(study))
    expect(other.conditions.filter(r => r.k > 120).map(r => r.pWin)).not.toEqual(study.conditions.filter(r => r.k > 120).map(r => r.pWin))
  })

  it('the same games give the same study', () => {
    expect(walkForwardProjection(games, 'M', OPTIONS)).toEqual(study)
  })
})

describe('how the variables move with the pace, and whether it is particular to each team', () => {
  it('the league slope says how much each thing moves per unit of pace over the usual one', () => {
    const slopes = leaguePaceSlopes(all, 'M')
    expect(Object.keys(slopes).sort()).toEqual([...RESPONSE_KEYS].sort())
    for (const key of RESPONSE_KEYS) expect(Number.isFinite(slopes[key])).toBe(true)
  })

  it('the reliability of the slope of a team is the correlation of the slopes of its odd and its even games, for what it makes and what it lets make', () => {
    const r = splitHalf(all, 'M')
    for (const key of RESPONSE_KEYS) for (const side of ['attack', 'defence'] as const) {
      expect(r[key][side]).toBeGreaterThanOrEqual(-1)
      expect(r[key][side]).toBeLessThanOrEqual(1)
    }
  })

  it('the correlation is Pearson\'s (by hand)', () => {
    expect(pearson([1, 2, 3], [2, 4, 6])).toBeCloseTo(1, 12)
    expect(pearson([1, 2, 3], [3, 2, 1])).toBeCloseTo(-1, 12)
    expect(pearson([1, 2, 3, 4], [1, 3, 2, 4])).toBeCloseTo(0.8, 12)
    expect(pearson([1, 1, 1], [1, 2, 3])).toBeNaN()
  })
})

describe('what the rival does when the condition is put on us (#940)', () => {
  const model = buildModel(all, 'M')
  const r = rivalResponse(all, 'M')

  it('in the league: the correlation, over every side of every game, of what the rival made over its expectation with what we made over ours, and of the points of both (by hand)', () => {
    expect(r.league.efficiency).toBeCloseTo(pearson(model.pool.map(s => s.oRiv), model.pool.map(s => s.oOwn)), 12)
    const sides = all.filter(g => g.homeRow && g.awayRow).flatMap(g => [[g.homePoints, g.awayPoints], [g.awayPoints, g.homePoints]])
    expect(r.league.points).toBeCloseTo(pearson(sides.map(([, opp]) => opp), sides.map(([pts]) => pts)), 12)
    expect(r.league.efficiency).toBeGreaterThan(0)
  })

  it('whether the response is particular to each team: correlations of its odd and its even games, between -1 and 1', () => {
    for (const key of ['efficiency', 'points', 'wins'] as const) {
      expect(r.reliability[key]).toBeGreaterThanOrEqual(-1)
      expect(r.reliability[key]).toBeLessThanOrEqual(1)
    }
  })

  it('the same games give the same answer', () => {
    expect(rivalResponse(all, 'M')).toEqual(r)
  })
})

describe('the section of the report', () => {
  it('has the parts of the evaluation and no NaN or undefined', () => {
    const study = walkForwardProjection(games, 'M', OPTIONS)
    const text = formatProjectionSection([{ name: 'PRIMERA', gender: 'M', games: games.length, projection: study, slopes: leaguePaceSlopes(games, 'M'), reliability: splitHalf(games, 'M'), rival: rivalResponse(all, 'M') }])
    for (const title of ['## Proyección multifactorial', 'Cómo se mueve el juego con el ritmo', 'Si es propio de cada equipo', 'Probabilidad con condiciones', 'Prever el resto del partido', 'Lo que hace el rival']) expect(text).toContain(title)
    expect(text).not.toMatch(/NaN|undefined/)
  })
})
