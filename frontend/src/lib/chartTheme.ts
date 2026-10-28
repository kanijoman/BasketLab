/**
 * Colours of the charts from the theme tokens (issue #188). Recharts writes them as SVG attributes and the PNG/PDF exports (html2canvas)
 * copy the DOM, so a chart takes the resolved colour of the theme in use, read from design/tokens.css, never `var(--x)` (an export would lose it).
 */
import { useMemo } from 'react'
import { useTheme, type Theme } from './theme'

/** The value of a token on <html> right now (empty outside a browser with the tokens loaded). */
export function cssColour(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

export interface ChartTheme {
  series: string[]          // --chart-1..8, in order
  grid: string
  axis: string
  reference: string         // reference and median lines
  surface: string
  ok: string
  warn: string
  bad: string
  text: string
  faint: string
  floor: string             // the floor of the court: a raised surface
  onData: string            // ink over a bubble of data colour
  tooltip: { backgroundColor: string; border: string; borderRadius: number; fontSize: number; color: string }
}

/** `theme` only says for which theme they are read: the values are the ones on <html> now. */
function readChartTheme(theme: Theme): ChartTheme {
  void theme
  const surface = cssColour('--surface')
  return {
    series: [1, 2, 3, 4, 5, 6, 7, 8].map(i => cssColour(`--chart-${i}`)),
    grid: cssColour('--line'),
    axis: cssColour('--text-muted'),
    reference: cssColour('--text-faint') || cssColour('--text-muted'),
    surface,
    ok: cssColour('--ok'),
    warn: cssColour('--warn'),
    bad: cssColour('--bad'),
    text: cssColour('--text'),
    faint: cssColour('--text-faint'),
    floor: cssColour('--surface-raised'),
    onData: cssColour('--on-data'),
    tooltip: { backgroundColor: surface, border: `1px solid ${cssColour('--line')}`, borderRadius: 8, fontSize: 12, color: cssColour('--text') },
  }
}

/** The chart colours of the theme in use; a component that uses it is drawn again when the theme changes. */
export function useChartTheme(): ChartTheme {
  const { theme } = useTheme()
  return useMemo(() => readChartTheme(theme), [theme])
}
