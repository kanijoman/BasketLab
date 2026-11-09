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
      zone('key_area', { rating: 'above', fg_pct: 30 }),   // 30 % but above league → green
      zone('short_mid_range', { rating: 'below', fg_pct: 70 }), // 70 % but below league → red
      zone('medium_mid_range', { rating: 'average' }),
    ]))
    expect(colours).toContain('#1a7f37')                 // ok
    expect(colours).toContain('#cf222e')                 // bad
    expect(colours).toContain('#9a6700')                 // warn
  })

  it('does not use a hue computed from the raw percentage', () => {
    expect(court([zone('key_area', { rating: 'average', fg_pct: 38 })]).innerHTML).not.toMatch(/hsl\(/)
  })

  it('shows a legend with the three ratings in zones mode', () => {
    const text = court([zone('key_area', { rating: 'above' })]).textContent ?? ''
    expect(text).toMatch(/encima/i)
    expect(text).toMatch(/promedio/i)
    expect(text).toMatch(/debajo/i)
  })

  it('flags zones with a small sample', () => {
    expect(court([zone('key_area', { rating: 'above', low_sample: true, fga: 3 })]).querySelector('[data-low-sample="true"]')).not.toBeNull()
  })
})

// Issue #196 (U6): the court is the page's, not a dark box: its floor, lines, rim and data colours are the tokens of the theme in use.
describe('FibaCourtSVG theme (issue #196)', () => {
  it('light: a light floor with dark lines, and the data tones of the light theme', () => {
    const c = court([zone('key_area', { rating: 'above' })])
    const svg = c.querySelector('svg') as SVGElement
    expect(svg.style.background).toBe('rgb(240, 243, 246)')                       // --surface-raised
    expect(c.querySelector('line')?.getAttribute('stroke')).toBe('#59636e')       // --text-muted
    expect(c.querySelector('circle[r="6.75"]')?.getAttribute('stroke')).toBe('#ea580c')   // the rim, --chart-1
    expect(fills(c)).toContain('#1a7f37')
  })

  it('dark: the same court with the tokens of the dark theme', () => {
    inTheme('dark')
    const c = court([zone('key_area', { rating: 'above' })])
    expect((c.querySelector('svg') as SVGElement).style.background).toBe('rgb(28, 33, 40)')
    expect(c.querySelector('line')?.getAttribute('stroke')).toBe('#8b949e')
    expect(c.querySelector('circle[r="6.75"]')?.getAttribute('stroke')).toBe('#f97316')
    expect(fills(c)).toContain('#3fb950')
  })

  it('the text on a bubble is the ink made for data colours: readable on both', () => {
    const light = court([zone('key_area', { rating: 'above' })]).querySelector('text')?.getAttribute('fill')
    inTheme('dark')
    const dark = court([zone('key_area', { rating: 'above' })]).querySelector('text')?.getAttribute('fill')
    expect([light, dark]).toEqual(['#ffffff', '#0d1117'])
  })

  it('scatter: made and missed shots use the good and the bad tone of the theme', () => {
    const shots = [{ x: 50, y: 50, made: true }, { x: 40, y: 60, made: false }] as unknown as ShotRawData[]
    const colours = fills(court([], 'scatter', shots))
    expect(colours).toContain('#1a7f37')
    expect(colours).toContain('#cf222e')
  })

  it('has no colour of its own in its markup: no hex outside the tokens', () => {
    const html = court([zone('key_area', { rating: 'above' })]).innerHTML
    expect(html).not.toMatch(/#(?:cccccc|1a1a2e|ff8c00|4ade80|f87171|2E9E4F)/i)
    expect(html).not.toMatch(/rgba\(255,\s*255,\s*255/)
  })
})

// Issue #452, block 2 (zones): the court draws a bubble for each zone of the engine (what the app and the scouting say); the old system of the web is gone (step 3).
describe('the zones of the engine on the court', () => {
  const ENGINE = ['restricted_area', 'key_area', 'short_mid_range', 'medium_mid_range', 'long_mid_range', 'left_corner_three', 'left_wing_three', 'center_three', 'right_wing_three', 'right_corner_three']
  const LEGACY = ['paint', 'mid_left', 'mid_center', 'mid_right', 'corner_left', 'wing_left', 'top_three', 'wing_right', 'corner_right']

  it('draws one bubble per zone of the engine', () => {
    const container = court(ENGINE.map(key => zone(key)))
    expect(Array.from(container.querySelectorAll('g[data-zone]')).map(g => g.getAttribute('data-zone'))).toEqual(ENGINE)
  })

  it('draws nothing for the zones of the old system: only those of the engine are known (the data was republished with them, step 3)', () => {
    const container = court(LEGACY.map(key => zone(key)))
    expect(container.querySelectorAll('g[data-zone]')).toHaveLength(0)
  })

  it('no bubble is on top of another one: the anchors of the engine zones are apart', () => {
    const container = court(ENGINE.map(key => zone(key, { fga: 1 })))
    const centres = Array.from(container.querySelectorAll('g[data-zone]')).map(g => {
      const c = g.querySelector('circle')!
      return [Number(c.getAttribute('cx')), Number(c.getAttribute('cy'))]
    })
    for (let i = 0; i < centres.length; i++) for (let j = i + 1; j < centres.length; j++) {
      expect(Math.hypot(centres[i][0] - centres[j][0], centres[i][1] - centres[j][1])).toBeGreaterThan(40)
    }
  })
})

