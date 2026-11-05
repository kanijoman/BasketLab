import { describe, expect, it } from 'vitest'
import { INOUT_STATS, inoutRows, inoutVsRows } from './inoutExport'

// Issue #759: IN/OUT has no table, so its export is made of the same figures the cards show: one row per statistic with ON, OFF and the difference (ON − OFF).
const ON = { points_for: 105.4, points_against: 98, minutes: 320, net_rating: 7.5, offensive_rating: 110.2, defensive_rating: 102.7, fg2_made: 40, fg2_attempts: 80, fg2_percentage: 50 }
const OFF = { points_for: 100, points_against: 104, minutes: 280, net_rating: -2, offensive_rating: 98, defensive_rating: 100, fg2_made: 30, fg2_attempts: 70 }

describe('inoutRows', () => {
  it('one row per statistic of the cards, in their order, with ON, OFF and ON − OFF', () => {
    const rows = inoutRows(ON, OFF)
    expect(rows.map(r => r.stat)).toEqual(INOUT_STATS.map(s => s.label))
    expect(rows.find(r => r.stat === 'Net Rating')).toEqual({ stat: 'Net Rating', on: 7.5, off: -2, diff: 9.5 })
    expect(rows.find(r => r.stat === 'Pts a favor')).toEqual({ stat: 'Pts a favor', on: 105.4, off: 100, diff: 5.4 })     // 105.4 − 100 without the binary noise
    expect(rows.find(r => r.stat === 'DRtg')).toEqual({ stat: 'DRtg', on: 102.7, off: 100, diff: 2.7 })                   // the difference is ON − OFF whatever is better
  })

  it('a figure that a block does not have is empty, and so is its difference (never a zero that says something)', () => {
    const rows = inoutRows(ON, OFF)
    expect(rows.find(r => r.stat === 'T2 %')).toEqual({ stat: 'T2 %', on: 50, off: null, diff: null })
    expect(rows.find(r => r.stat === 'STL')).toEqual({ stat: 'STL', on: null, off: null, diff: null })
  })

  it('a zero is a figure, not an absence', () => {
    expect(inoutRows({ points_for: 0, points_against: 0, minutes: 0, assists: 0 }, { points_for: 0, points_against: 0, minutes: 0, assists: 3 }).find(r => r.stat === 'AST'))
      .toEqual({ stat: 'AST', on: 0, off: 3, diff: -3 })
  })

  it('a value that is not a number (text, NaN, null) is empty', () => {
    const rows = inoutRows({ points_for: 'x' as unknown as number, points_against: 1, minutes: NaN }, { points_for: 1, points_against: null as unknown as number, minutes: 5 })
    expect(rows.find(r => r.stat === 'Pts a favor')).toEqual({ stat: 'Pts a favor', on: null, off: 1, diff: null })
    expect(rows.find(r => r.stat === 'Minutos')).toEqual({ stat: 'Minutos', on: null, off: 5, diff: null })
  })
})

describe('inoutVsRows', () => {
  it('compares the ON of two players: player 1, player 2 and the first minus the second', () => {
    const rows = inoutVsRows(ON, { ...OFF, net_rating: 1.5 })
    expect(rows.find(r => r.stat === 'Net Rating')).toEqual({ stat: 'Net Rating', a: 7.5, b: 1.5, diff: 6 })
    expect(rows.map(r => r.stat)).toEqual(INOUT_STATS.map(s => s.label))
  })
})
