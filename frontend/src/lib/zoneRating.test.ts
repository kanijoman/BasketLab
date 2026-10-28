import { describe, expect, it } from 'vitest'
import { RATING_LABEL, ratingColor, ratingFromQuartiles, ratingTextClass, zoneColours } from './zoneRating'
import type { ChartTheme } from './chartTheme'

// The colours come from the theme in use (issue #196): a stand-in theme with the three data tones and the faint ink
const THEME = { ok: '#00aa00', warn: '#aaaa00', bad: '#aa0000', faint: '#777777' } as ChartTheme
const RATING_COLOR = zoneColours(THEME)

describe('zone rating helpers', () => {
  it('maps each rating to a distinct colour (the data tones: good, borderline, bad) and a Spanish label', () => {
    expect(RATING_COLOR).toEqual({ above: '#00aa00', average: '#aaaa00', below: '#aa0000' })
    expect(new Set(Object.values(RATING_COLOR)).size).toBe(3)
    expect(RATING_LABEL.above).toMatch(/encima/i)
    expect(RATING_LABEL.average).toMatch(/promedio/i)
    expect(RATING_LABEL.below).toMatch(/debajo/i)
  })

  it('uses a neutral grey when there is no rating', () => {
    expect(ratingColor(undefined, THEME)).toBe(ratingColor('none', THEME))
    expect(ratingColor('none', THEME)).toBe('#777777')
    expect(ratingColor('unknown', THEME)).not.toBe(RATING_COLOR.above)
    expect(ratingColor('above', THEME)).toBe(RATING_COLOR.above)
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
    expect(ratingTextClass('above')).toBe('text-ok')
    expect(ratingTextClass('below')).toBe('text-bad')
    expect(ratingTextClass('average')).toBe('text-warn')
    expect(ratingTextClass(undefined)).toBe('text-ink-muted')
  })
})
