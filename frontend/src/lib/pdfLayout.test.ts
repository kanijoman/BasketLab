import { describe, it, expect } from 'vitest'
import { collectBreakPoints, computePdfSlices } from './pdfLayout'

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

describe('computePdfSlices with break points (#134)', () => {
  // content width 269 mm over 1000 px → page 1 holds 168/0.269 ≈ 624 px, later pages ≈ 676 px
  const every100 = Array.from({ length: 39 }, (_, i) => (i + 1) * 100)

  it('cuts only at break points so rows are never split', () => {
    const s = computePdfSlices(1000, 4000, opts, every100)
    for (const sl of s.slice(0, -1)) expect(every100).toContain(Math.round(sl.srcY + sl.srcH))
    expect(s.length).toBeGreaterThan(1)
  })

  it('still covers the whole capture without gaps or overlaps', () => {
    const s = computePdfSlices(1000, 4000, opts, every100)
    expect(s[0].srcY).toBe(0)
    for (let i = 1; i < s.length; i++) expect(s[i].srcY).toBeCloseTo(s[i - 1].srcY + s[i - 1].srcH)
    const last = s[s.length - 1]
    expect(last.srcY + last.srcH).toBeCloseTo(4000)
  })

  it('never exceeds the page height', () => {
    for (const sl of computePdfSlices(1000, 4000, opts, every100)) {
      expect(sl.destY + sl.destH).toBeLessThanOrEqual(210 - 14 + 1e-6)
    }
  })

  it('falls back to a hard cut when an element is taller than a page', () => {
    // no break point between 100 and 3000: a single 2900 px block
    const s = computePdfSlices(1000, 4000, opts, [100, 3000, 3100])
    expect(s.length).toBeGreaterThan(2)
    expect(s[0].srcH).toBeLessThanOrEqual(625)
  })

  it('ignores a break point that would leave a page almost empty', () => {
    // first break at 50 px (8 % of a page) must not be used; hard cut instead
    const s = computePdfSlices(1000, 2000, opts, [50])
    expect(s[0].srcH).toBeGreaterThan(300)
  })

  it('behaves as before without break points', () => {
    expect(computePdfSlices(1000, 4000, opts)).toEqual(computePdfSlices(1000, 4000, opts, []))
  })
})

describe('collectBreakPoints', () => {
  function rect(top: number, height: number): DOMRect {
    return { top, bottom: top + height, height, left: 0, right: 0, width: 0, x: 0, y: top, toJSON: () => ({}) }
  }

  it('returns sorted unique row boundaries in canvas pixels', () => {
    const root = document.createElement('div')
    root.innerHTML = '<table><tbody><tr id="a"></tr><tr id="b"></tr></tbody></table><section id="c"></section>'
    root.getBoundingClientRect = () => rect(100, 400)
    const boxes: Record<string, DOMRect> = { a: rect(100, 40), b: rect(140, 40), c: rect(200, 60) }
    root.querySelectorAll('tr, section').forEach(el => {
      ;(el as HTMLElement).getBoundingClientRect = () => boxes[el.id]
    })
    expect(collectBreakPoints(root, 2)).toEqual([80, 160, 200, 320])
  })

  it('ignores zero-height elements and boundaries outside the element', () => {
    const root = document.createElement('div')
    root.innerHTML = '<ul><li id="a"></li><li id="z"></li></ul>'
    root.getBoundingClientRect = () => rect(0, 100)
    const boxes: Record<string, DOMRect> = { a: rect(0, 50), z: rect(50, 0) }
    root.querySelectorAll('li').forEach(el => {
      ;(el as HTMLElement).getBoundingClientRect = () => boxes[el.id]
    })
    expect(collectBreakPoints(root, 1)).toEqual([50])
  })
})
