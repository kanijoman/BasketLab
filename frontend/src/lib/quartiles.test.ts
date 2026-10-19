import { describe, expect, it } from 'vitest'
import { computeQuartileMap } from './quartiles'

describe('computeQuartileMap', () => {
  const rows = [{ a: 1, b: null }, { a: 2, b: 10 }, { a: 3, b: 20 }, { a: 4, b: 30 }, { a: 5, b: 40 }]

  it('gives the three quartile thresholds of every key', () => {
    expect(computeQuartileMap(rows, ['a'])).toEqual({ a: [2, 3, 4] })
  })

  it('ignores missing values', () => {
    expect(computeQuartileMap(rows, ['b']).b).toEqual([17.5, 25, 32.5])
  })

  it('has no colouring with fewer than four values', () => {
    expect(computeQuartileMap([{ a: 1 }, { a: 2 }, { a: 3 }], ['a']).a).toEqual([0, 0, 0])
  })

  it('keeps zeros: a team with no points after steals is the worst, not missing data', () => {
    expect(computeQuartileMap([{ a: 0 }, { a: 0 }, { a: 4 }, { a: 8 }], ['a']).a).toEqual([0, 2, 5])
  })
})
