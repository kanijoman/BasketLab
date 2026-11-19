/**
 * Helpers for html2canvas exports.
 *
 * html2canvas cannot rasterise cross-origin images that lack CORS headers (e.g. the
 * FEB photo CDN), so they come out blank. Components mark such elements with
 * EXPORT_HIDE_ATTR and provide an EXPORT_ONLY_ATTR replacement; `prepareCloneForExport`
 * swaps them inside the cloned document only, leaving the on-screen UI untouched.
 */

export const EXPORT_HIDE_ATTR = 'data-export-hide'
export const EXPORT_ONLY_ATTR = 'data-export-only'

/** Tailwind's `line-clamp-N` (`display: -webkit-box` + `overflow: hidden`): html2canvas does not clamp it, it paints every line inside a box cut at the height of the cell. */
const CLAMPED = '[class*="line-clamp-"]'

/** Use as html2canvas `onclone` callback. */
export function prepareCloneForExport(doc: Document): void {
  doc.querySelectorAll<HTMLElement>(`[${EXPORT_HIDE_ATTR}]`).forEach(el => {
    el.style.display = 'none'
  })
  doc.querySelectorAll<HTMLElement>(`[${EXPORT_ONLY_ATTR}]`).forEach(el => {
    el.style.display = 'inline-flex'
  })
  // an exported table shows the whole text (on screen it is clamped with its tooltip): a plain block, as tall as its lines
  doc.querySelectorAll<HTMLElement>(CLAMPED).forEach(el => {
    el.style.display = 'block'
    el.style.overflow = 'visible'
    el.style.maxHeight = 'none'
    el.style.setProperty('-webkit-line-clamp', 'unset')
  })
}
