import { describe, expect, it } from 'vitest'
import { Scores, brier, calibrationTable, logLoss, multiclassBrier, rps } from './metrics'

// The scores of the walk-forward evaluation (#851): what a probability is judged with.
describe('logLoss and brier', () => {
  it('are the usual ones for a win and a loss, and for a tie (half)', () => {
    expect(logLoss(0.8, 1)).toBeCloseTo(-Math.log(0.8), 12)
    expect(logLoss(0.8, 0)).toBeCloseTo(-Math.log(0.2), 12)
    expect(brier(0.8, 1)).toBeCloseTo(0.04, 12)
    expect(brier(0.8, 0)).toBeCloseTo(0.64, 12)
    expect(logLoss(0.5, 0.5)).toBeCloseTo(Math.log(2), 12)
    expect(brier(0.3, 0.5)).toBeCloseTo(0.04, 12)
  })

  it('a certain wrong answer is finite: the log loss is capped, never infinite', () => {
    expect(Number.isFinite(logLoss(0, 1))).toBe(true)
    expect(Number.isFinite(logLoss(1, 0))).toBe(true)
    expect(logLoss(0, 1)).toBeGreaterThan(20)
  })

  it('a coin toss is ln 2 and 0.25 whatever happens', () => {
    expect(logLoss(0.5, 1)).toBeCloseTo(Math.LN2, 12)
    expect(brier(0.5, 0)).toBe(0.25)
  })
})

describe('the scores of several classes', () => {
  it('multiclass Brier is the sum of the squares over the classes', () => {
    expect(multiclassBrier([0.2, 0.5, 0.3], 1)).toBeCloseTo(0.04 + 0.25 + 0.09, 12)
    expect(multiclassBrier([0, 1, 0], 1)).toBe(0)
  })

  it('the ranked probability score looks at the cumulative distribution: being one place off costs less than being three off', () => {
    expect(rps([0.2, 0.5, 0.3], 1)).toBeCloseTo(((0.2 - 0) ** 2 + (0.7 - 1) ** 2) / 2, 12)
    expect(rps([1, 0, 0, 0], 0)).toBe(0)
    expect(rps([0, 1, 0, 0], 0)).toBeLessThan(rps([0, 0, 0, 1], 0))
    expect(rps([0.25, 0.25, 0.25, 0.25], 2)).toBeCloseTo((0.25 ** 2 + 0.5 ** 2 + 0.25 ** 2) / 3, 12)
  })
})

describe('Scores', () => {
  it('keeps the means of what it is given, and says how many', () => {
    const s = new Scores()
    s.add({ logLoss: 1, brier: 0.2, hit: true })
    s.add({ logLoss: 3, brier: 0.4, hit: false })
    expect(s.n).toBe(2)
    expect(s.mean('logLoss')).toBe(2)
    expect(s.mean('brier')).toBeCloseTo(0.3, 12)
    expect(s.rate('hit')).toBe(0.5)
  })

  it('has nothing to say when it has nothing', () => {
    expect(Number.isNaN(new Scores().mean('logLoss'))).toBe(true)
  })
})

describe('the calibration table', () => {
  it('groups the forecasts in bins of probability with their mean and what happened', () => {
    const table = calibrationTable([{ p: 0.1, y: 0 }, { p: 0.12, y: 0 }, { p: 0.15, y: 1 }, { p: 0.9, y: 1 }, { p: 0.95, y: 1 }], 5)
    expect(table).toHaveLength(2)
    expect(table[0]).toMatchObject({ n: 3, from: 0, to: 0.2 })
    expect(table[0].predicted).toBeCloseTo((0.1 + 0.12 + 0.15) / 3, 12)
    expect(table[0].actual).toBeCloseTo(1 / 3, 12)
    expect(table[1]).toMatchObject({ n: 2, actual: 1 })
  })

  it('a probability of exactly one belongs to the last bin', () => {
    expect(calibrationTable([{ p: 1, y: 1 }], 5)[0]).toMatchObject({ from: 0.8, to: 1, n: 1 })
  })

  it('is empty without forecasts', () => {
    expect(calibrationTable([], 5)).toEqual([])
  })
})
