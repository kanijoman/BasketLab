import { describe, it, expect } from 'vitest'
import { computePdfSlices } from './pdfLayout'

// A4 landscape, 14 mm margins, content starts at 28 mm on page 1.
const opts = { pageW: 297, pageH: 210, margin: 14, firstTop: 28 }

describe('computePdfSlices', () => {
  it('keeps a short capture on a single page', () => {
    const s = computePdfSlices(1000, 300, opts)
    expect(s).toHaveLength(1)
    expect(s[0]).toMatchObject({ srcY: 0, srcH: 300, destY: 28 })
  })

  it('splits a tall capture across pages without losing any pixel (issue #86 regression)', () => {
    const s = computePdfSlices(1000, 4000, opts)
    expect(s.length).toBeGreaterThan(1)
    expect(s[0].srcY).toBe(0)
    for (let i = 1; i < s.length; i++) expect(s[i].srcY).toBeCloseTo(s[i - 1].srcY + s[i - 1].srcH)
    const last = s[s.length - 1]
    expect(last.srcY + last.srcH).toBeCloseTo(4000)
  })

  it('never draws below the bottom margin and uses the full content width', () => {
    const scale = (297 - 28) / 1000
    for (const sl of computePdfSlices(1000, 4000, opts)) {
      expect(sl.destY + sl.destH).toBeLessThanOrEqual(210 - 14 + 1e-6)
      expect(sl.destH).toBeCloseTo(sl.srcH * scale)
    }
  })

  it('returns no slices for an empty capture', () => {
    expect(computePdfSlices(0, 0, opts)).toEqual([])
  })
})
