import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { cssColour, useChartTheme } from './chartTheme'
import { useTheme } from './theme'

// The real tokens are not loaded in jsdom: two themes that only differ in what the charts read are enough.
const STYLE = `
  :root[data-theme="light"] { --chart-1: #ea580c; --chart-2: #0969da; --line: #d0d7de; --text-muted: #59636e; --surface: #ffffff; --bg: #f6f8fa; --ok: #1a7f37; --bad: #cf222e; --warn: #9a6700; --text: #1f2328; --text-faint: #6e7781; --on-data: #ffffff; --surface-raised: #f0f3f6 }
  :root[data-theme="dark"]  { --chart-1: #f97316; --chart-2: #58a6ff; --line: #30363d; --text-muted: #8b949e; --surface: #161b22; --bg: #0d1117; --ok: #3fb950; --bad: #f85149; --warn: #d29922; --text: #e6edf3; --text-faint: #6e7681; --on-data: #0d1117; --surface-raised: #1c2128 }
`
let style: HTMLStyleElement

beforeEach(() => {
  localStorage.clear()
  style = document.createElement('style')
  style.textContent = STYLE
  document.head.appendChild(style)
  document.documentElement.setAttribute('data-theme', 'light')
})
afterEach(() => style.remove())

// Issue #188: recharts writes its colours as SVG attributes and the PNG/PDF exports copy the DOM, so a chart needs the
// resolved colour of the theme in use (not `var(--x)`), and a new one when the theme changes.
describe('chart colours (issue #188)', () => {
  it('are the tokens of the theme in use', () => {
    const { result } = renderHook(() => useChartTheme())
    expect(result.current.series.slice(0, 2)).toEqual(['#ea580c', '#0969da'])
    expect(result.current.grid).toBe('#d0d7de')
    expect(result.current.axis).toBe('#59636e')
    expect(result.current.tooltip.backgroundColor).toBe('#ffffff')
    expect(result.current.ok).toBe('#1a7f37')
    expect(result.current).toMatchObject({ warn: '#9a6700', text: '#1f2328', faint: '#6e7781', onData: '#ffffff', floor: '#f0f3f6' })     // what the court draws with (#196)
  })

  it('change with the theme', () => {
    const { result } = renderHook(() => ({ chart: useChartTheme(), theme: useTheme() }))
    act(() => result.current.theme.setPreference('dark'))
    expect(result.current.chart.series[0]).toBe('#f97316')
    expect(result.current.chart.tooltip.backgroundColor).toBe('#161b22')
  })

  it('reads one token for the moment of an export (its background)', () => {
    expect(cssColour('--bg')).toBe('#f6f8fa')
  })
})
