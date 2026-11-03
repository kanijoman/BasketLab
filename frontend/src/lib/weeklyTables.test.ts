import { describe, expect, it } from 'vitest'
import { PAPER } from '@design/paper'
import { svgSize } from './svgImage'
import { tableSvg } from './weeklyTables'

// The tables of the weekly report as an image (issue #716, D4b): the rows of `weeklyRows` drawn as an SVG in the colours of the paper, which `svgToPng` turns into the PNG of the ZIP.
const HEADERS = ['Equipo', 'PJ', 'Pts/P']
const ROWS = { texts: [['Alfa & Beta <1>', '12', '78.4 (+2.1)'], ['Gamma', '3', '70.0']], tones: [['plain', 'plain', 'q1'], ['plain', 'plain', 'q4']] as const }

describe('the table as an image', () => {
  it('is a standalone SVG with the title, the headers and every cell, the text escaped', () => {
    const svg = tableSvg(HEADERS, { texts: ROWS.texts, tones: ROWS.tones.map(r => [...r]) }, 'Estadísticas Básicas - Toda la Competición')
    expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true)
    expect(svg).toContain('font-family="Helvetica')
    for (const text of ['Estadísticas Básicas - Toda la Competición', 'Equipo', 'PJ', 'Pts/P', 'Alfa &amp; Beta &lt;1&gt;', '78.4 (+2.1)', 'Gamma']) expect(svg).toContain(`>${text}<`)
    expect(svg).not.toContain('Alfa & Beta')
  })

  it('paints the quartiles with the colours of the paper: the best green, the worst red, and no tint where there is no rating', () => {
    const svg = tableSvg(HEADERS, { texts: ROWS.texts, tones: ROWS.tones.map(r => [...r]) }, 't')
    expect(svg).toContain(`data-tone="q1" fill="${PAPER.ok}"`)
    expect(svg).toContain(`data-tone="q4" fill="${PAPER.bad}"`)
    expect(svg).toContain(`data-tone="plain" fill="${PAPER.surface}"`)
    expect(svg).toContain(`fill="${PAPER.surfaceRaised}"`)                     // the header
  })

  it('has a size to rasterise that grows with the rows and with the text of the columns', () => {
    const small = svgSize(tableSvg(HEADERS, { texts: [ROWS.texts[0]], tones: [['plain', 'plain', 'plain']] }, 't'))!
    const tall = svgSize(tableSvg(HEADERS, { texts: [...ROWS.texts, ...ROWS.texts], tones: [...ROWS.tones, ...ROWS.tones].map(r => [...r]) }, 't'))!
    const wide = svgSize(tableSvg(HEADERS, { texts: [['A muy larga denominación de un club de baloncesto', '1', '2']], tones: [['plain', 'plain', 'plain']] }, 't'))!
    expect(tall.height).toBeGreaterThan(small.height)
    expect(wide.width).toBeGreaterThan(small.width)
  })

  it('says «Sin datos» when there are no rows, as the server did, and the title says why', () => {
    const svg = tableSvg(HEADERS, { texts: [], tones: [] }, 'Estadísticas Básicas (datos insuficientes)')
    expect(svg).toContain('>Sin datos<')
    expect(svg).toContain('(datos insuficientes)')
    expect(svgSize(svg)).not.toBeNull()
  })
})
