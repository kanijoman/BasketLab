import { describe, expect, it } from 'vitest'
import { buildGames } from '../gameLog'
import { buildModel } from '../pool'
import { buildProjection } from './build'
import { project } from './project'
import { conditionsParam, defaultConditions, fromInput, MAX_CONDITIONS, parseConditions, parseNumber, suggestedInput, toInput } from './query'
import type { Condition } from './variables'
import { primera } from '@/test/forecastFixtures'

// The conditions of the card «¿Y si…?» (#940) in the address, so that a preview with its questions can be shared and reloaded: `?si=own.points.gt.70_rival.efg.lt.40`. The page writes the
// shares and the free throws per 100 (40 is 40 %) and the rest as they are; what the address cannot be read as is left out, never an error.
const c = (variable: Condition['variable'], op: Condition['op'], value: number): Condition => ({ variable, op, value })

describe('the conditions in the address', () => {
  it('go and come back: the variable, «more than» or «less than», and the value as the page writes it', () => {
    const conditions = [c('own.points', 'gt', 70), c('rival.efg', 'lt', 0.4), c('game.possessions', 'gt', 78.5)]
    const text = conditionsParam(conditions)
    expect(text).toBe('own.points.gt.70_rival.efg.lt.40_game.possessions.gt.78.5')
    expect(parseConditions(text)).toEqual(conditions)
  })

  it('a share is written as a percentage and read back to the same ratio (no drift)', () => {
    for (const value of [0.4, 0.185, 0.2125, 0.333]) {
      const [back] = parseConditions(conditionsParam([c('own.tov', 'lt', value)]))
      expect(back.value).toBeCloseTo(value, 12)
    }
  })

  it('what cannot be read is left out: an unknown variable or direction, a value that is not a number, an empty part', () => {
    expect(parseConditions('own.points.gt.70_own.height.gt.2_rival.efg.eq.40_own.tov.lt.abc__game.possessions.lt.')).toEqual([c('own.points', 'gt', 70)])
    expect(parseConditions('')).toEqual([])
    expect(parseConditions(null)).toEqual([])
  })

  it(`no more than ${MAX_CONDITIONS}: the first ones`, () => {
    const text = 'own.points.gt.70_rival.points.lt.60_own.efg.gt.45_rival.tov.gt.15'
    expect(parseConditions(text)).toHaveLength(MAX_CONDITIONS)
    expect(parseConditions(text).map(x => x.variable)).toEqual(['own.points', 'rival.points', 'own.efg'])
  })
})

describe('the values the page writes', () => {
  it('a share and the free throws are per 100, the rest as they are', () => {
    expect(toInput(c('own.efg', 'gt', 0.465))).toBeCloseTo(46.5, 12)
    expect(toInput(c('rival.ftr', 'lt', 0.3))).toBeCloseTo(30, 12)
    expect(toInput(c('own.points', 'gt', 70))).toBe(70)
    expect(fromInput('own.orb', 'gt', 32)).toEqual(c('own.orb', 'gt', 0.32))
    expect(fromInput('own.oer', 'lt', 95.5)).toEqual(c('own.oer', 'lt', 95.5))
  })

  it('a number is read with the decimal comma or point; anything else is not a number', () => {
    expect(parseNumber('40,5')).toBe(40.5)
    expect(parseNumber(' 70 ')).toBe(70)
    expect(parseNumber('18.25')).toBe(18.25)
    for (const text of ['', 'abc', '4,0,1', '-3', '1e3x']) expect(parseNumber(text)).toBeNull()
  })
})

describe('what the card starts with', () => {
  const f = primera()
  const model = buildModel(buildGames(f.team_rows), f.gender)
  const ids = [...new Set(model.games.flatMap(g => [g.home, g.away]))]
  const p = buildProjection(model, ids[0], ids[1], 'own')!
  const expected = (id: Condition['variable']) => project(p, []).profile.find(r => r.variable === id)!.expected

  it('a value is suggested from what is expected of this matchup: the points whole, a share to one decimal', () => {
    expect(suggestedInput(p, 'own.points')).toBe(Math.round(expected('own.points')))
    expect(suggestedInput(p, 'rival.efg')).toBeCloseTo(Math.round(1000 * expected('rival.efg')) / 10, 12)
  })

  it('without conditions in the address, one: our points over what is expected', () => {
    expect(defaultConditions(p)).toEqual([c('own.points', 'gt', Math.round(expected('own.points')))])
  })
})
