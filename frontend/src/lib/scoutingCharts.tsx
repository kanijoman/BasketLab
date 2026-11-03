// The shot charts of the individual scouting DOCX (issue #717, 17c): the court of the web (`FibaCourtSVG`, the zones and the heatmap) drawn with the colours of the paper and written as a
// standalone SVG, which `svgImage` makes a PNG. The DOCX is white whatever theme the screen is in, so the colours are the ones of `design/paper.ts`, not the ones in use.
import { renderToStaticMarkup } from 'react-dom/server'
import { PAPER } from '@design/paper'
import FibaCourtSVG from '@/components/ui/FibaCourtSVG'
import type { ChartTheme } from '@/lib/chartTheme'
import type { ShotRawData, ShotZoneData } from '@/api/client'

/** The chart theme of the paper: every colour a chart of the web asks of the theme, in the tones of the light one. */
export function paperChartTheme(): ChartTheme {
  return {
    series: [PAPER.heatHot, PAPER.heatCool, PAPER.ok, PAPER.warn, PAPER.own, PAPER.conceded, PAPER.bad, PAPER.muted],
    grid: PAPER.line, axis: PAPER.muted, reference: PAPER.faint, surface: PAPER.surface,
    ok: PAPER.ok, warn: PAPER.warn, bad: PAPER.bad, text: PAPER.ink, faint: PAPER.faint, floor: PAPER.surfaceRaised, onData: PAPER.onData,
    tooltip: { backgroundColor: PAPER.surface, border: `1px solid ${PAPER.line}`, borderRadius: 8, fontSize: 12, color: PAPER.ink },
  }
}

/** The half court as a standalone SVG (with its namespace, to be an image): the zones of the player with their percentage and rating, or the heatmap of his shots. */
export function courtSvg(mode: 'zones' | 'heatmap', zones: ShotZoneData[], shots: ShotRawData[]): string {
  const markup = renderToStaticMarkup(<FibaCourtSVG theme={paperChartTheme()} vizMode={mode} zones={zones} rawShots={shots} />)
  return markup.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg" font-family="Helvetica, Arial, sans-serif"')
}
