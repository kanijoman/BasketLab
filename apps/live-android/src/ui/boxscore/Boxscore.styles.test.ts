import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const read = (...path: string[]) => readFileSync(join(__dirname, ...path), 'utf8').split(String.fromCharCode(13)).join('')      // the files may have Windows line ends
const css = read('..', '..', 'styles.css')
const tokens = read('..', '..', '..', '..', '..', 'design', 'tokens.css')

function rule(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

/** The tokens of each theme, as the file says them: the dark block, the light one under prefers-color-scheme and the forced light one. */
function theme(header: string): Record<string, string> {
  const start = tokens.indexOf(header)
  const block = tokens.slice(start, tokens.indexOf('}', start))
  return Object.fromEntries([...block.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map(m => [m[1], m[2]]))
}
const THEMES = {
  dark: theme(':root,\n:root[data-theme="dark"] {'),
  light: theme(':root:not([data-theme="dark"]) {'),
  forcedLight: theme(':root[data-theme="light"] {'),
}

const channels = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
const luminance = (rgb: number[]) => {
  const [r, g, b] = rgb.map(v => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a: number[], b: number[]) => { const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05) }
/** ``color-mix(in srgb, tone share%, base)``. */
const mix = (tone: string, share: number, base: string) => channels(tone).map((t, i) => t * share + channels(base)[i] * (1 - share))

describe('box score styles (issue #593)', () => {
  it('the table moves sideways inside its own box and the name of the player stays, on an opaque background', () => {
    expect(rule('.bx-scroll')).toContain('overflow-x: auto')
    expect(rule('.bx-table .bx-name')).toMatch(/position: sticky/)
    expect(rule('.bx-table .bx-name')).toMatch(/left: 0/)
    expect(rule('.bx-table th, .bx-table td')).toMatch(/background: var\(--card\)/)         // otherwise the figures show through the name when they pass under it
  })

  it('the hidden texts of the cells stay inside the box that scrolls: they are positioned from it, so they cannot stretch the page', () => {
    // found in the e2e of a phone: the absolutely positioned «por encima de su media» of the cells sat far to the right of the scrolled table, the page became wider
    // than the screen and the bar of tabs, fixed to the page, left the screen («Acerca de» cut)
    expect(rule('.bx-scroll')).toMatch(/position: relative/)
  })

  it('a figure above his average mixes the green of the theme into the colour of the table and one below mixes its red', () => {
    expect(rule('.bx-table td[data-dev="up"]')).toMatch(/color-mix\(in srgb, var\(--ok\) calc\(var\(--dev-abs\) \* var\(--dev-max\) \* 100%\), var\(--card\)\)/)
    expect(rule('.bx-table td[data-dev="down"]')).toMatch(/color-mix\(in srgb, var\(--dev-bad\) calc\(var\(--dev-abs\) \* var\(--dev-max\) \* 100%\), var\(--card\)\)/)
  })

  it('what has no deviation keeps the colour of the table: white in light and dark in dark', () => {
    expect(css).not.toMatch(/\.bx-table td\s*\{[^}]*background: color-mix/)
  })

  it('the flash of the last action stops when the user asks for less movement', () => {
    expect(css).toMatch(/prefers-reduced-motion: reduce\) \{ \.bx-table td\.bump \{ animation: none/)
  })

  it('every theme has the red and the green of the gradient', () => {
    for (const colors of Object.values(THEMES)) {
      expect(colors['--dev-bad']).toMatch(/^#/)
      expect(colors['--ok']).toMatch(/^#/)
    }
  })

  it.each(Object.entries(THEMES))('the text is readable on the strongest tint of both colours in %s (WCAG AA, 4.5)', (_name, colors) => {
    const max = Number(/--dev-max:\s*([\d.]+)/.exec(css)?.[1])
    for (const tone of [colors['--ok'], colors['--dev-bad']]) {
      expect(contrast(channels(colors['--text']), mix(tone, max, colors['--surface']))).toBeGreaterThanOrEqual(4.5)
    }
  })
})
