import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// Issue #633 (from U7, #197): the colours the app draws read in both themes (WCAG 2.1 AA: 4.5 for text). The web measures the shared tokens in designTokens.test.ts; this is
// the same for what only the app draws: the severity and category of an alert over their own tint, the pace colours, the orange of the active tab and of the selected
// option (the orange *text*, `--accent-text`, not the fill) and the ink of a filled button.
const read = (...path: string[]) => readFileSync(join(__dirname, ...path), 'utf8').split(String.fromCharCode(13)).join('')       // the files may have Windows line ends
const css = read('..', 'styles.css')
const tokens = read('..', '..', '..', '..', 'design', 'tokens.css')

/** The tokens of one theme, as the file says them. */
function theme(header: string): Map<string, string> {
  const start = tokens.indexOf(header)
  const block = tokens.slice(start, tokens.indexOf('}', start))
  return new Map([...block.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map(m => [m[1], m[2]]))
}
const THEMES = { dark: theme(':root,\n:root[data-theme="dark"] {'), light: theme(':root[data-theme="light"] {') }

const channels = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16))
const luminance = (hex: string) => {
  const [r, g, b] = channels(hex).map(v => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const contrast = (a: string, b: string) => { const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05) }
/** ``rgb(tone / alpha)`` over a base, as the CSS paints it. */
const tint = (tone: string, alpha: number, base: string) =>
  '#' + channels(tone).map((t, i) => Math.round(t * alpha + channels(base)[i] * (1 - alpha)).toString(16).padStart(2, '0')).join('')

const SURFACES = ['--bg', '--surface', '--surface-raised']
const SEVERITY: [string, number[]][] = [['--sev-critical', [0.14, 0.12]], ['--sev-warning', [0.14, 0.08]], ['--sev-info', [0.12]]]    // the alphas of styles.css
const CATEGORIES = [...THEMES.dark.keys()].filter(k => k.startsWith('--cat-'))

describe.each(Object.entries(THEMES))('the colours of the app read in the %s theme (issue #633)', (_name, b) => {
  const at = (token: string) => b.get(token)!

  it('the text, the orange text, the data colours and the pace read on the page, the cards and the raised rows', () => {
    const wrong = ['--text', '--text-muted', '--accent-text', '--ok', '--dev-bad', '--pace-fast', '--pace-slow', ...SEVERITY.map(([t]) => t), ...CATEGORIES]
      .flatMap(token => SURFACES.filter(s => contrast(at(token), at(s)) < 4.5).map(s => `${token} on ${s}: ${contrast(at(token), at(s)).toFixed(2)}`))
    expect(wrong).toEqual([])
  })

  it('the severity of an alert reads over its own tint, on the page and on the cards', () => {
    const wrong = SEVERITY.flatMap(([token, alphas]) => alphas.flatMap(alpha => ['--bg', '--surface'].flatMap(s => {
      const ratio = contrast(at(token), tint(at(token), alpha, at(s)))
      return ratio < 4.5 ? [`${token} on its ${alpha} tint over ${s}: ${ratio.toFixed(2)}`] : []
    })))
    expect(wrong).toEqual([])
  })

  it('the category of an alert reads over its tint (12 %), on the page and on the cards', () => {
    const wrong = CATEGORIES.flatMap(token => ['--bg', '--surface'].flatMap(s => {
      const ratio = contrast(at(token), tint(at(token), 0.12, at(s)))
      return ratio < 4.5 ? [`${token} on its tint over ${s}: ${ratio.toFixed(2)}`] : []
    }))
    expect(wrong).toEqual([])
  })

  it('the orange text reads over the tint of the update notice and the selected option, and the ink of a filled button over its fill', () => {
    for (const alpha of [0.12, 0.2]) for (const s of ['--bg', '--surface']) {
      expect(contrast(at('--accent-text'), tint(at('--accent'), alpha, at(s))), `accent-text on accent/${alpha} over ${s}`).toBeGreaterThanOrEqual(4.5)
    }
    expect(contrast(at('--accent-ink'), at('--accent-solid'))).toBeGreaterThanOrEqual(4.5)
  })
})

describe('what styles.css paints with the orange (issue #633)', () => {
  it('the orange of a text is --accent-text, never --accent (which is the fill: white on it is 3.6 in the light theme)', () => {
    expect(css.match(/(?<![\w-])color:\s*var\(--accent\)/g)).toBeNull()
  })

  it('a filled button (selected segment, pressed verdict) is --accent-solid with the ink of --accent-ink', () => {
    expect(css.match(/background:\s*var\(--accent\);\s*color:\s*var\(--accent-ink\)/g)).toBeNull()
  })
})

// The rest of what #633 asked of the accessibility of the app: the keyboard (and a switch or a pad of a tablet) sees where it is, and the movement stops on request.
describe('focus and movement in styles.css (issue #633)', () => {
  it('what has the focus is drawn with the --focus ring of the suite, which reads (3:1 for a component) over the page and the cards in both themes', () => {
    expect(css).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--focus\)/)
    expect(css).not.toMatch(/outline:\s*(none|0)/)                         // nothing turns the ring off
    for (const b of Object.values(THEMES)) for (const s of ['--bg', '--surface']) expect(contrast(b.get('--focus')!, b.get(s)!), `--focus on ${s}`).toBeGreaterThanOrEqual(3)
  })

  it('with prefers-reduced-motion the transition of the team box stops too, not only the animations', () => {
    const reduce = css.split('prefers-reduced-motion: reduce').slice(1).map(part => part.slice(0, 300)).join(' ')                  // what each block of reduced motion says
    expect(reduce).toMatch(/\.team[^{]*\{[^}]*transition:\s*none/)
  })
})
