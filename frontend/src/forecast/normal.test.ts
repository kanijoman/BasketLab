import { describe, expect, it } from 'vitest'
import { bisect, erf, phi } from './normal'
import vectors from '../../../tests/local_vectors/forecast.json'

// `math.erf` of Python over the whole range, edges of the pieces of the function included (tests/local_vectors/forecast.json): the win probability is `0.5 * (1 + erf(z / sqrt 2))`
// and the port must not move a probability by more than the rounding of the page.
describe('erf answers what Python answers', () => {
  it.each((vectors.erf as [number, number][]).map(([x, want]) => [x, want] as const))('erf(%s)', (x, want) => {
    expect(Math.abs(erf(x) - want)).toBeLessThan(1e-14)
  })

  it('is odd, bounded and exact at the ends', () => {
    expect(erf(0)).toBe(0)
    expect(erf(0.3)).toBe(-erf(-0.3))
    expect(erf(Infinity)).toBe(1)
    expect(erf(-Infinity)).toBe(-1)
    expect(erf(30)).toBe(1)
    expect(Number.isNaN(erf(NaN))).toBe(true)
  })
})

describe('phi, the normal distribution function', () => {
  it('is half at zero, symmetric and the known values', () => {
    expect(phi(0)).toBe(0.5)
    expect(phi(1.2815515655446004)).toBeCloseTo(0.9, 12)
    expect(phi(-1.96) + phi(1.96)).toBeCloseTo(1, 14)
    expect(phi(1.959963984540054)).toBeCloseTo(0.975, 12)
  })
})

describe('bisect', () => {
  it('finds the root of an increasing function inside its bracket', () => {
    expect(bisect(x => x * x * x - 2, 0, 3, 1e-12)).toBeCloseTo(2 ** (1 / 3), 10)
    expect(bisect(x => x - 5, -100, 100, 1e-12)).toBeCloseTo(5, 10)
  })

  it('answers the nearest end when the root is outside the bracket (the caller then knows it cannot anchor)', () => {
    expect(bisect(x => x + 10, 0, 5, 1e-12)).toBe(0)
    expect(bisect(x => x - 10, 0, 5, 1e-12)).toBe(5)
  })
})
