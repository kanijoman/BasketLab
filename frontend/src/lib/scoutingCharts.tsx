// The shot charts of the individual scouting DOCX (issue #717, 17c): the court of the web (`FibaCourtSVG`, the zones and the heatmap) drawn with the colours of the paper and written as a
// standalone SVG, which `svgImage` makes a PNG. The DOCX is white whatever theme the screen is in, so the colours are the ones of `design/paper.ts`, not the ones in use.
import { renderToStaticMarkup } from 'react-dom/server'
import { PAPER } from '@design/paper'
import FibaCourtSVG from '@/components/ui/FibaCourtSVG'
import type { ChartTheme } from '@/lib/chartTheme'
import type { ShotRawData, ShotZoneData } from '@/api/client'
import { svgSize } from '@/lib/svgImage'

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

const TITLE_LINE = 24

/** A chart with the lines of its title above it (the shot charts of the weekly report say whose they are and the shots made out of those taken), as a standalone SVG of the chart's width. */
export function titledSvg(svg: string, lines: string[]): string {
  const size = svgSize(svg)
  if (!size) throw new Error('El gráfico no declara su tamaño.')
  const head = TITLE_LINE * lines.length + 12
  const escape = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const text = lines.map((line, i) => `<text x="${size.width / 2}" y="${TITLE_LINE * (i + 1)}" text-anchor="middle" font-size="${i ? 14 : 17}" font-weight="${i ? 'normal' : 'bold'}" fill="${PAPER.ink}">${escape(line)}</text>`).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size.width} ${size.height + head}" width="${size.width}" height="${size.height + head}" font-family="Helvetica, Arial, sans-serif">`
    + `<rect width="${size.width}" height="${size.height + head}" fill="${PAPER.surface}"/>${text}<g transform="translate(0,${head})">${svg.replace(' xmlns="http://www.w3.org/2000/svg"', '')}</g></svg>`
}
