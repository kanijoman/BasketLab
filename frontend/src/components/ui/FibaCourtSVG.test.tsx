import { render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import FibaCourtSVG from './FibaCourtSVG'
import { THEME_KEY } from '@/lib/theme'
import type { ShotRawData, ShotZoneData } from '@/api/client'

const zone = (key: string, over: Partial<ShotZoneData> = {}): ShotZoneData => ({
  zone: key, zone_label: key, points: 2, fga: 40, fgm: 20, fg_pct: 50, ...over,
})

// The real tokens are not loaded in jsdom: the ones the court reads, in both themes (issue #196, U6).
const TOKENS = `
  :root[data-theme="light"] { --surface-raised: #f0f3f6; --text: #1f2328; --text-muted: #59636e; --text-faint: #6e7781; --ok: #1a7f37; --warn: #9a6700; --bad: #cf222e;
    --on-data: #ffffff; --chart-1: #ea580c; --chart-2: #0969da; --line: #d0d7de; --surface: #ffffff; --bg: #f6f8fa }
  :root[data-theme="dark"]  { --surface-raised: #1c2128; --text: #e6edf3; --text-muted: #8b949e; --text-faint: #6e7681; --ok: #3fb950; --warn: #d29922; --bad: #f85149;
    --on-data: #0d1117; --chart-1: #f97316; --chart-2: #58a6ff; --line: #30363d; --surface: #161b22; --bg: #0d1117 }
`
let style: HTMLStyleElement
const inTheme = (theme: 'light' | 'dark') => {
  localStorage.setItem(THEME_KEY, theme)
  document.documentElement.setAttribute('data-theme', theme)
}
beforeEach(() => { style = document.createElement('style'); style.textContent = TOKENS; document.head.appendChild(style); inTheme('light') })
afterEach(() => { style.remove(); document.documentElement.removeAttribute('data-theme') })

function court(zones: ShotZoneData[], mode: 'zones' | 'scatter' | 'heatmap' = 'zones', rawShots?: ShotRawData[]) {
  return render(<FibaCourtSVG zones={zones} vizMode={mode} rawShots={rawShots} />).container
}
const fills = (container: HTMLElement) => Array.from(container.querySelectorAll('circle')).map(c => c.getAttribute('fill') ?? '')

describe('FibaCourtSVG zone colours', () => {
  it('colours zones by their rating against the league, not by a fixed FG%', () => {
    const colours = fills(court([
      zone('paint', { rating: 'above', fg_pct: 30 }),   // 30 % but above league → green
      zone('mid_left', { rating: 'below', fg_pct: 70 }), // 70 % but below league → red
      zone('mid_right', { rating: 'average' }),
    ]))
    expect(colours).toContain('#1a7f37')                 // ok
    expect(colours).toContain('#cf222e')                 // bad
    expect(colours).toContain('#9a6700')                 // warn
  })

  it('does not use a hue computed from the raw percentage', () => {
    expect(court([zone('paint', { rating: 'average', fg_pct: 38 })]).innerHTML).not.toMatch(/hsl\(/)
  })

  it('shows a legend with the three ratings in zones mode', () => {
    const text = court([zone('paint', { rating: 'above' })]).textContent ?? ''
    expect(text).toMatch(/encima/i)
    expect(text).toMatch(/promedio/i)
    expect(text).toMatch(/debajo/i)
  })

  it('flags zones with a small sample', () => {
    expect(court([zone('paint', { rating: 'above', low_sample: true, fga: 3 })]).querySelector('[data-low-sample="true"]')).not.toBeNull()
  })
})

// Issue #196 (U6): the court is the page's, not a dark box: its floor, lines, rim and data colours are the tokens of the theme in use.
describe('FibaCourtSVG theme (issue #196)', () => {
  it('light: a light floor with dark lines, and the data tones of the light theme', () => {
    const c = court([zone('paint', { rating: 'above' })])
    const svg = c.querySelector('svg') as SVGElement
    expect(svg.style.background).toBe('rgb(240, 243, 246)')                       // --surface-raised
    expect(c.querySelector('line')?.getAttribute('stroke')).toBe('#59636e')       // --text-muted
    expect(c.querySelector('circle[r="6.75"]')?.getAttribute('stroke')).toBe('#ea580c')   // the rim, --chart-1
    expect(fills(c)).toContain('#1a7f37')
  })

  it('dark: the same court with the tokens of the dark theme', () => {
    inTheme('dark')
    const c = court([zone('paint', { rating: 'above' })])
    expect((c.querySelector('svg') as SVGElement).style.background).toBe('rgb(28, 33, 40)')
    expect(c.querySelector('line')?.getAttribute('stroke')).toBe('#8b949e')
    expect(c.querySelector('circle[r="6.75"]')?.getAttribute('stroke')).toBe('#f97316')
    expect(fills(c)).toContain('#3fb950')
  })

  it('the text on a bubble is the ink made for data colours: readable on both', () => {
    const light = court([zone('paint', { rating: 'above' })]).querySelector('text')?.getAttribute('fill')
    inTheme('dark')
    const dark = court([zone('paint', { rating: 'above' })]).querySelector('text')?.getAttribute('fill')
    expect([light, dark]).toEqual(['#ffffff', '#0d1117'])
  })

  it('scatter: made and missed shots use the good and the bad tone of the theme', () => {
    const shots = [{ x: 50, y: 50, made: true }, { x: 40, y: 60, made: false }] as unknown as ShotRawData[]
    const colours = fills(court([], 'scatter', shots))
    expect(colours).toContain('#1a7f37')
    expect(colours).toContain('#cf222e')
  })

  it('has no colour of its own in its markup: no hex outside the tokens', () => {
    const html = court([zone('paint', { rating: 'above' })]).innerHTML
    expect(html).not.toMatch(/#(?:cccccc|1a1a2e|ff8c00|4ade80|f87171|2E9E4F)/i)
    expect(html).not.toMatch(/rgba\(255,\s*255,\s*255/)
  })
})
