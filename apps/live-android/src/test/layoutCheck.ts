/** The layout rules every screen of the app must meet (issue #508): nothing sticks out of the screen and no text or button sits on top of another one.
 *  The geometry is pure (and tested); the e2e collects the boxes of the page in the browser (`collectBoxes`) and calls `layoutProblems`. */

export interface Box {
  id: string
  /** The visible text of the element ('' for a container). */
  text: string
  left: number
  top: number
  right: number
  bottom: number
  /** The `id` of the closest ancestor that is also in the list (an element inside another is not an overlap). */
  parent: string | null
  button?: boolean
}

/** Overlap tolerated as rounding or border (px per side). */
const TOLERANCE = 2

const sized = (b: Box) => b.right - b.left > 0 && b.bottom - b.top > 0

function overlaps(a: Box, b: Box): boolean {
  return Math.min(a.right, b.right) - Math.max(a.left, b.left) > TOLERANCE && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > TOLERANCE
}

function related(a: Box, b: Box, byId: Map<string, Box>): boolean {
  const chain = (box: Box) => { const ids = new Set<string>(); for (let p = box.parent; p; p = byId.get(p)?.parent ?? null) ids.add(p); return ids }
  return chain(a).has(b.id) || chain(b).has(a.id)
}

/** What is wrong with the layout, one sentence per problem (empty = fine). `width` is the width of the viewport. */
export function layoutProblems(boxes: Box[], width: number): string[] {
  const visible = boxes.filter(sized)
  const byId = new Map(visible.map(b => [b.id, b]))
  const problems: string[] = []
  for (const b of visible) if (b.right > width + TOLERANCE) problems.push(`«${b.id}» sale de la pantalla por la derecha (${Math.round(b.right)} > ${width})`)
  const leaves = visible.filter(b => b.text !== '' || b.button)
  for (let i = 0; i < leaves.length; i++) {
    for (let j = i + 1; j < leaves.length; j++) {
      const a = leaves[i], b = leaves[j]
      if (!related(a, b, byId) && overlaps(a, b)) problems.push(`«${a.id}» se superpone con «${b.id}»`)
    }
  }
  return problems
}

/** Runs in the browser (page.evaluate): the boxes of the elements that show text or are buttons. Serialised by Playwright, so it must not use anything outside. */
export function collectBoxes(): Box[] {
  const boxes: Box[] = []
  const owner = new Map<Element, string>()
  const all = Array.from(document.querySelectorAll('body *')).filter(el => {
    const style = getComputedStyle(el)
    // the bar of tabs is fixed over the page on purpose: what scrolls under it is not an overlap
    const fixed = (e: Element | null): boolean => (e ? getComputedStyle(e).position === 'fixed' || fixed(e.parentElement) : false)
    return style.display !== 'none' && style.visibility !== 'hidden' && !fixed(el) && !['SCRIPT', 'STYLE', 'SVG', 'PATH', 'OPTION'].includes(el.tagName.toUpperCase())
  })
  all.forEach((el, i) => owner.set(el, `${el.tagName.toLowerCase()}#${i}`))
  for (const el of all) {
    const rect = el.getBoundingClientRect()
    const own = Array.from(el.childNodes).filter(n => n.nodeType === Node.TEXT_NODE).map(n => (n.textContent ?? '').trim()).join(' ').trim()
    let parent: string | null = null
    for (let p = el.parentElement; p; p = p.parentElement) if (owner.has(p)) { parent = owner.get(p)!; break }
    const label = (own || el.getAttribute('aria-label') || el.tagName.toLowerCase()).slice(0, 40)
    boxes.push({ id: `${label} [${owner.get(el)}]`, text: own, left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, parent: parent ? boxes.find(b => b.id.endsWith(`[${parent}]`))?.id ?? null : null,
      button: el.tagName === 'BUTTON' || el.getAttribute('role') === 'button' })
  }
  return boxes
}
