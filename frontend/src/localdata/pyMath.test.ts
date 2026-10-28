import { describe, expect, it } from 'vitest'
import { pyRound } from './pyMath'

// Python's round(x, n) is "banker's" on the exact binary value; Math.round and toFixed round exact ties up. The advanced figures of the API are
// rounded with Python, so the local ones must agree on every tie (issue #327).
describe('pyRound', () => {
  it.each([
    [12.25, 1, 12.2], [12.35, 1, 12.3], [0.125, 2, 0.12], [0.375, 2, 0.38], [2.5, 0, 2], [3.5, 0, 4], [-12.25, 1, -12.2],   // exact ties: to even
    [1.15, 1, 1.1], [2.675, 2, 2.67], [1.005, 2, 1],                                                                         // not ties in binary
    [47.04999999999, 1, 47], [47.06, 1, 47.1], [0, 1, 0], [-0.04, 1, -0],
  ])('round(%s, %s) = %s', (x, n, expected) => {
    expect(pyRound(x, n)).toBe(expected)
  })
})
