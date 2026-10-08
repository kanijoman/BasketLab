/** Pagination helper for image-based PDF exports (jsPDF). */

export interface PdfLayout {
  pageW: number
  pageH: number
  margin: number
  /** y (mm) where content starts on the first page (below the header) */
  firstTop: number
}

export interface PdfSlice {
  /** source rows in the captured canvas (px) */
  srcY: number
  srcH: number
  /** destination on the page (mm) */
  destY: number
  destH: number
}

/** A page is not cut earlier than this fraction of its capacity, to avoid nearly empty pages. */
const MIN_FILL = 0.5

/**
 * Split an imgW×imgH px capture, scaled to the content width, into per-page slices.
 * With ``breakPoints`` (canvas px where a cut is harmless, e.g. row boundaries) every page
 * ends at the last break point that fits, so rows are not split; if none fits (an element
 * taller than a page) it falls back to a hard cut.
 */
export function computePdfSlices(imgW: number, imgH: number, l: PdfLayout, breakPoints: number[] = []): PdfSlice[] {
  if (imgW <= 0 || imgH <= 0) return []
  const scale = (l.pageW - 2 * l.margin) / imgW // mm per px
  const slices: PdfSlice[] = []
  let srcY = 0
  let top = l.firstTop
  while (srcY < imgH - 1e-6) {
    const cap = (l.pageH - l.margin - top) / scale
    const srcEnd = pickEnd(srcY, cap, imgH, breakPoints)
    const srcH = srcEnd - srcY
    slices.push({ srcY, srcH, destY: top, destH: srcH * scale })
    srcY = srcEnd
    top = l.margin
  }
  return slices
}

function pickEnd(srcY: number, cap: number, imgH: number, breakPoints: number[]): number {
  const hardEnd = srcY + cap
  if (hardEnd >= imgH) return imgH
  const fits = breakPoints.filter(b => b > srcY + cap * MIN_FILL && b <= hardEnd)
  return fits.length ? Math.max(...fits) : hardEnd
}

const BREAK_SELECTOR = 'tr, li, section, h2, h3, [data-pdf-break]'

/** Vertical boundaries (canvas px, ``scale`` = canvas/CSS ratio) of the rows/blocks inside ``root``. */
export function collectBreakPoints(root: HTMLElement, scale: number): number[] {
  const base = root.getBoundingClientRect()
  const limit = base.height * scale
  const points = new Set<number>()
  root.querySelectorAll<HTMLElement>(BREAK_SELECTOR).forEach(el => {
    const r = el.getBoundingClientRect()
    if (r.height <= 0) return
    for (const y of [(r.top - base.top) * scale, (r.bottom - base.top) * scale]) {
      if (y > 0 && y < limit) points.add(Math.round(y))
    }
  })
  return [...points].sort((a, b) => a - b)
}
