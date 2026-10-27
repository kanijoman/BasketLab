/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

// Issue #188: the colours of the web come from design/tokens.css (shared with the live app), so both themes work everywhere.
// A colour written in a component only fits the theme it was picked for: this guard keeps them out.
const SRC = __dirname
const DESIGN = join(__dirname, '..', '..', 'design')
const tokens = readFileSync(join(DESIGN, 'tokens.css'), 'utf8')
const preset = readFileSync(join(DESIGN, 'tailwind-preset.cjs'), 'utf8')

/** Files that may still carry their own colours, and why. The list only shrinks. */
const EXCEPTIONS: Record<string, string> = {
  'components/ui/FibaCourtSVG.tsx': 'the court is drawn dark on purpose in both themes until U6 (#196) gives it its own tokens',
  'lib/zoneRating.ts': 'the colours of the zones are those of the court (dark in both themes) and of its legend, until U6 (#196)',
}

const PALETTE = 'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose'
const FORBIDDEN: [string, RegExp][] = [
  ['a hex colour', /#[0-9a-fA-F]{3,8}\b/],
  ['an rgb() colour', /rgba?\(\s*\d/],
  ['a Tailwind palette colour', new RegExp(`(?<![\\w-])(?:[\\w-]+:)*(?:bg|text|border(?:-[trblxy])?|ring(?:-offset)?|from|via|to|fill|stroke|divide|outline|placeholder|decoration|shadow|caret)-(?:${PALETTE})-\\d{2,3}\\b`)],
  ['an old name of the web palette', /(?<![\w-])(?:[\w-]+:)*[\w-]*-(?:surface-(?:base|border|hover)|ink-(?:primary|secondary)|brand-\d+|accent-\d+|court-\d+|primary-\d+)\b|(?<![\w-])(?:text|bg|border)-(?:up|down)\b/],
  ['a dark: variant (the tokens already change with the theme)', /(?<![\w-])dark:/],
  // jsPDF takes a colour as three numbers too: the PDF painted a fixed dark page that way, uncaught (#617)
  ['a colour as numbers for jsPDF', /set(?:Fill|Text|Draw)Color\(\s*\d+\s*,/],
]

const stripComments = (code: string) => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1')

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'test' ? [] : sources(path)
    return /\.(tsx?|css)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [path] : []
  })
}

function offences(file: string): string[] {
  const code = stripComments(readFileSync(file, 'utf8'))
  return FORBIDDEN.flatMap(([what, re]) => {
    const match = code.match(re)
    return match ? [`${what}: ${match[0]}`] : []
  })
}

describe('colours of the web (issue #188)', () => {
  const files = sources(SRC).map(file => [relative(SRC, file).replace(/\\/g, '/'), file] as const)

  it('has no colour outside the tokens in any component, page or stylesheet', () => {
    const found = files.filter(([name]) => !(name in EXCEPTIONS)).flatMap(([name, file]) => offences(file).map(o => `${name} → ${o}`))
    expect(found).toEqual([])
  })

  it.each(Object.keys(EXCEPTIONS))('%s is still an exception (when it is fixed, take it off the list)', name => {
    expect(offences(join(SRC, name)).length).toBeGreaterThan(0)
  })

  // White text was right on the dark surfaces only: in the light theme it vanished (the title of Análisis Predictivo).
  it('puts white text only on a coloured fill', () => {
    const FILL = /(?<![\w-])bg-(?:accent-solid|accent-hover|bad|ok|warn|secondary|secondary-hover|chart-\d)(?![\w/-])/
    const OWN_FILL = /backgroundColor|background:/                // a chip painted with its own colour (team, player)
    const white = files.flatMap(([name, file]) => stripComments(readFileSync(file, 'utf8')).split('\n')
      .map((line, i, lines) => ({ line, around: lines.slice(Math.max(0, i - 1), i + 7).join('\n') }))
      .filter(({ line }) => /(?<![\w-])(?:[\w:-]+:)?text-white\b/.test(line))
      .filter(({ line, around }) => !FILL.test(line) && !OWN_FILL.test(around))
      .map(({ line }) => `${name} → ${line.trim().slice(0, 90)}`))
    expect(white).toEqual([])
  })

  // Tailwind drops a class it does not know without a word: `bg-surface-card` left inputs and tooltips without a background for months.
  it('uses only colour names that exist in the preset', () => {
    const FAMILIES = 'canvas|surface|line|ink|accent|secondary|focus|ok|bad|warn|chart|q[1-4]'
    const NAME = new RegExp(`(?<![\\w-])(?:[\\w\\[\\]&:().-]+:)*(?:bg|text|border(?:-[trblxy])?|ring(?:-offset)?|from|via|to|fill|stroke|divide|outline|placeholder|decoration|caret|shadow)-((?:${FAMILIES})(?:-[a-z0-9]+)?)(?:/\\d+)?(?![\\w-])`, 'g')
    const known = new Set(['canvas', 'surface', 'surface-raised', 'line', 'ink', 'ink-muted', 'ink-faint', 'accent', 'accent-ink', 'accent-text',
      'accent-solid', 'accent-hover', 'secondary', 'secondary-text', 'secondary-hover', 'focus', 'ok', 'bad', 'warn',
      ...[1, 2, 3, 4, 5, 6, 7, 8].map(i => `chart-${i}`), ...[1, 2, 3, 4].flatMap(q => [`q${q}-bg`, `q${q}-text`])])
    const unknown = files.flatMap(([name, file]) => [...stripComments(readFileSync(file, 'utf8')).matchAll(NAME)]
      .filter(m => !known.has(m[1])).map(m => `${name} → ${m[0]}`))
    expect(unknown).toEqual([])
    for (const name of known) expect(preset, name).toMatch(new RegExp(`\\b${name.split('-')[0]}\\b`))
  })
})

// ── design/tokens.css ─────────────────────────────────────────────────────────
type Block = Map<string, string>
function blocks(): Record<'dark' | 'lightSystem' | 'lightForced', Block> {
  const body = (start: string) => {
    const from = tokens.indexOf(start)
    const open = tokens.indexOf('{', tokens.indexOf('{', from) + (start.startsWith('@media') ? 1 : 0))
    let depth = 0
    for (let i = open; i < tokens.length; i++) {
      if (tokens[i] === '{') depth++
      if (tokens[i] === '}' && --depth === 0) return tokens.slice(open + 1, i)
    }
    throw new Error(`${start} not closed`)
  }
  const vars = (css: string): Block => new Map([...css.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map(m => [m[1], m[2].trim()]))
  return { dark: vars(body(':root,')), lightSystem: vars(body('@media (prefers-color-scheme: light)')), lightForced: vars(body(':root[data-theme="light"]')) }
}
const isColour = (value: string) => /^#|^rgba?\(|^\d+ \d+ \d+$|^0 \d/.test(value)
const channels = (hex: string) => {
  const h = hex.replace('#', '')
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)).join(' ')
}

describe('design/tokens.css (issue #188)', () => {
  const themes = blocks()

  it.each(Object.keys(themes) as (keyof typeof themes)[])('the -rgb channels of %s say the same colour as the hex', theme => {
    const block = themes[theme]
    const wrong = [...block].filter(([name]) => name.endsWith('-rgb'))
      .filter(([name, value]) => block.has(name.slice(0, -4)) && channels(block.get(name.slice(0, -4))!) !== value)
    expect(wrong).toEqual([])
  })

  it('the light theme sets every colour the dark one sets, both ways it can be chosen', () => {
    const colours = [...themes.dark].filter(([, v]) => isColour(v)).map(([n]) => n).sort()
    expect([...themes.lightSystem.keys()].sort()).toEqual(colours)
    expect([...themes.lightForced].sort()).toEqual([...themes.lightSystem].sort())
  })

  it('every token the Tailwind preset uses exists', () => {
    const used = [...preset.matchAll(/var\((--[\w-]+)\)|channel\('([\w-]+)'\)/g)].map(m => m[1] ?? `--${m[2]}-rgb`)
    expect(used.filter(name => !themes.dark.has(name))).toEqual([])
  })
})
