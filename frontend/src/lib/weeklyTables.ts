// The tables of the weekly report as an image (issue #716, D4b): the rows of `weeklyRows` drawn as an SVG with the colours of the paper (`design/paper.ts`), which `svgToPng` makes the
// PNG of the ZIP. The server drew them with matplotlib on a dark background; the browser has no matplotlib and the web is light by default, so the table is the one of the paper:
// white, the quartiles as a tint of the green / yellow / orange / red of the palette, and the figures in ink.
import { PAPER } from '@design/paper'
import type { TableRows, Tone } from '@/lib/weeklyRows'

const FILL: Record<Tone, string> = { plain: PAPER.surface, q1: PAPER.ok, q2: PAPER.warn, q3: PAPER.conceded, q4: PAPER.bad, even: PAPER.surfaceRaised }
const TINT: Record<Tone, number> = { plain: 1, q1: 0.22, q2: 0.22, q3: 0.22, q4: 0.22, even: 1 }

const FONT = 13
const CHAR = 7.4                       // the width of a character of 13 px Helvetica, on average (digits are narrower and capitals wider)
const PAD = 10
const ROW = 26
const TITLE = 40

const escape = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const widthOf = (text: string) => Math.ceil(text.length * CHAR) + 2 * PAD

/** The table as a standalone SVG (with its namespace, to be an image): the title, the headers and a row per team or player, each cell tinted by its tone. */
export function tableSvg(headers: string[], rows: TableRows, title: string): string {
  const widths = headers.map((header, c) => Math.max(widthOf(header), ...rows.texts.map(row => widthOf(row[c] ?? ''))))
  const width = Math.max(widths.reduce((a, b) => a + b, 0), widthOf(title), 320)
  const height = TITLE + ROW * (rows.texts.length + 1) + (rows.texts.length ? 0 : 60)
  const parts = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" font-family="Helvetica, Arial, sans-serif" font-size="${FONT}">`,
    `<rect width="${width}" height="${height}" fill="${PAPER.surface}"/>`,
    `<text x="${PAD}" y="26" font-size="16" font-weight="bold" fill="${PAPER.ink}">${escape(title)}</text>`]
  const cell = (c: number, y: number, label: string, tone: Tone | 'head', x: number) => {
    const left = c === 0, textX = left ? x + PAD : x + widths[c] / 2
    const fill = tone === 'head' ? PAPER.surfaceRaised : FILL[tone]
    const tint = tone === 'head' ? 1 : TINT[tone]
    parts.push(`<rect data-tone="${tone}" fill="${fill}" fill-opacity="${tint}" x="${x}" y="${y}" width="${widths[c]}" height="${ROW}" stroke="${PAPER.line}"/>`,
      `<text x="${textX}" y="${y + ROW / 2 + 5}" text-anchor="${left ? 'start' : 'middle'}" fill="${PAPER.ink}"${tone === 'head' ? ' font-weight="bold"' : ''}>${escape(label)}</text>`)
  }
  let x = 0
  headers.forEach((header, c) => { cell(c, TITLE, header, 'head', x); x += widths[c] })
  rows.texts.forEach((row, r) => {
    x = 0
    headers.forEach((_, c) => { cell(c, TITLE + ROW * (r + 1), row[c] ?? '', rows.tones[r]?.[c] ?? 'plain', x); x += widths[c] })
  })
  if (!rows.texts.length) parts.push(`<text x="${width / 2}" y="${TITLE + ROW + 36}" text-anchor="middle" fill="${PAPER.muted}">Sin datos</text>`)
  parts.push('</svg>')
  return parts.join('')
}
