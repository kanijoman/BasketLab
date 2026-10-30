import { describe, expect, it } from 'vitest'
import { npMean, npStd, pyRound } from './pyMath'

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

// NumPy sums pairwise, so the mean of these 40 values is 4.5075 and the sequential sum gives 4.507499999999999 (the IFQ of the lineups divides by a standard deviation that depends on it).
describe('npMean and npStd (what np.mean and np.std give, in the last bit too)', () => {
  const forty = [29.5, -25.7, 10.0, -1.8, -0.4, 2.4, -19.2, 2.2, -5.4, 44.9, 7.7, 0.8, 1.6, -3.0, -7.7, 0.3, 10.8, 2.1, 16.5, 2.6, 5.3, 23.5, 11.5, -1.1, 2.8, 11.5, 28.2, 1.8, 2.1, 17.0, -5.6, 1.5,
    15.6, 12.0, 6.1, 13.0, -28.9, 17.3, -6.5, -15.0]
  it.each([
    [forty, 4.5075, 13.920746881902566],                                                          // blocks of eight
    [[0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.7], 0.15, 0.16583123951776998],     // eight and a remainder
    [[8.3, 13.4, -0.3, -7.9, 5.3, 4.4, 21.9, 14.0, 7.3], 7.377777777777776, 8.147361914929244],
  ])('%j', (values, mean, std) => {
    expect(npMean(values)).toBe(mean)
    expect(npStd(values)).toBe(std)
  })

  it('a list shorter than eight is summed in order and a long one in halves', () => {
    expect(npStd([5, 5, 5])).toBe(0)
    const long = Array.from({ length: 300 }, (_, i) => ((i * 37) % 101) / 10)
    expect(npMean(long)).toBeCloseTo(long.reduce((a, b) => a + b, 0) / 300, 12)
  })
})
