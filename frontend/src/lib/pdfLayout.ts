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

/** Split an imgW×imgH px capture, scaled to the content width, into per-page slices. */
export function computePdfSlices(imgW: number, imgH: number, l: PdfLayout): PdfSlice[] {
  if (imgW <= 0 || imgH <= 0) return []
  const scale = (l.pageW - 2 * l.margin) / imgW // mm per px
  const slices: PdfSlice[] = []
  let srcY = 0
  let top = l.firstTop
  while (srcY < imgH - 1e-6) {
    const availMm = l.pageH - l.margin - top
    const srcH = Math.min(imgH - srcY, availMm / scale)
    slices.push({ srcY, srcH, destY: top, destH: srcH * scale })
    srcY += srcH
    top = l.margin
  }
  return slices
}
