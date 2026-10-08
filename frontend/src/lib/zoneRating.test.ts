import { describe, expect, it } from 'vitest'
import { RATING_COLOR, RATING_LABEL, ratingColor, ratingFromQuartiles, ratingTextClass } from './zoneRating'

describe('zone rating helpers', () => {
  it('maps each rating to a distinct colour and a Spanish label', () => {
    expect(new Set(Object.values(RATING_COLOR)).size).toBe(3)
    expect(RATING_LABEL.above).toMatch(/encima/i)
    expect(RATING_LABEL.average).toMatch(/promedio/i)
    expect(RATING_LABEL.below).toMatch(/debajo/i)
  })

  it('uses a neutral grey when there is no rating', () => {
    expect(ratingColor(undefined)).toBe(ratingColor('none'))
    expect(ratingColor('unknown')).not.toBe(RATING_COLOR.above)
    expect(ratingColor('above')).toBe(RATING_COLOR.above)
  })

  it('rates a value against league quartiles (above Q3 / below Q1 / otherwise average)', () => {
    const q = { q1: 30, q2: 36, q3: 42 }
    expect(ratingFromQuartiles(50, q)).toBe('above')
    expect(ratingFromQuartiles(20, q)).toBe('below')
    expect(ratingFromQuartiles(36, q)).toBe('average')
  })

  it('has no rating without quartiles', () => {
    expect(ratingFromQuartiles(40, undefined)).toBe('unknown')
  })

  it('returns text classes per rating', () => {
    expect(ratingTextClass('above')).toContain('green')
    expect(ratingTextClass('below')).toContain('red')
    expect(ratingTextClass('average')).toContain('yellow')
    expect(ratingTextClass(undefined)).toContain('ink-secondary')
  })
})
