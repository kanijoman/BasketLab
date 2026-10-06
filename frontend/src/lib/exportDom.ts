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

/** Use as html2canvas `onclone` callback. */
export function prepareCloneForExport(doc: Document): void {
  doc.querySelectorAll<HTMLElement>(`[${EXPORT_HIDE_ATTR}]`).forEach(el => {
    el.style.display = 'none'
  })
  doc.querySelectorAll<HTMLElement>(`[${EXPORT_ONLY_ATTR}]`).forEach(el => {
    el.style.display = 'inline-flex'
  })
}
