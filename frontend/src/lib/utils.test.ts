import { describe, it, expect } from 'vitest'
import { fmt, fmtPct, cn } from './utils'

describe('fmt', () => {
  it('returns — for null', () => {
    expect(fmt(null)).toBe('—')
  })

  it('returns — for undefined', () => {
    expect(fmt(undefined)).toBe('—')
  })

  it('returns — for NaN', () => {
    expect(fmt(NaN)).toBe('—')
  })

  it('formats to 1 decimal by default', () => {
    expect(fmt(82.456)).toBe('82.5')
  })

  it('formats 0 correctly', () => {
    expect(fmt(0)).toBe('0.0')
  })

  it('respects custom decimal places', () => {
    expect(fmt(3.14159, 2)).toBe('3.14')
    expect(fmt(100, 0)).toBe('100')
  })
})

describe('fmtPct', () => {
  it('returns — for null', () => {
    expect(fmtPct(null)).toBe('—')
  })

  it('formats percentage with 1 decimal', () => {
    expect(fmtPct(34.2)).toBe('34.2%')
  })

  it('formats 0%', () => {
    expect(fmtPct(0)).toBe('0.0%')
  })
})

describe('cn', () => {
  it('merges class names', () => {
    const result = cn('foo', 'bar')
    expect(result).toContain('foo')
    expect(result).toContain('bar')
  })

  it('handles conditional classes', () => {
    expect(cn('base', false && 'hidden')).not.toContain('hidden')
    expect(cn('base', true && 'visible')).toContain('visible')
  })
})
