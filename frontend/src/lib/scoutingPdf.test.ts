import { describe, expect, it } from 'vitest'
import { scoutingCalls, scoutingPdf, scoutingSafe } from './scoutingPdf'
import type { ScoutingReport } from '@/api/scoutingRival'
import vectors from '../../../tests/local_vectors/scouting_pdf.json'

// The PDF of the rival scouting in the browser (issue #715). The layout of the server (`scouting_pdf.lay_out`) was run over a recorder for several reports (`tests/local_vectors/
// scouting_pdf_vectors.py`): the web must ask for the same calls, in the same order, with the same texts, widths and colours; what jsPDF draws from them is the browser's.
describe('the layout asks for what the server\'s layout asks for', () => {
  it.each(vectors.cases.map(c => [c.name, c] as const))('%s', (_name, c) => {
    expect(scoutingCalls(c.report as unknown as ScoutingReport, c.own_name)).toEqual(c.calls)
  })
})

describe('the text the standard fonts can write', () => {
  it.each(vectors.safe.map(([input, expected]) => [JSON.stringify(input), input, expected] as const))('%s', (_label, input, expected) => {
    expect(scoutingSafe(input)).toBe(expected)
  })
})

describe('the PDF', () => {
  it('is a PDF with the team, the sections and the table cells, and draws every case without failing', async () => {
    const full = vectors.cases[0]
    const blob = await scoutingPdf(full.report as unknown as ScoutingReport, { subtitle: 'LF Challenge', ownName: full.own_name, compress: false })
    expect(blob.type).toBe('application/pdf')
    const text = new TextDecoder('latin1').decode(await blob.arrayBuffer())
    expect(text.startsWith('%PDF')).toBe(true)
    for (const word of ['Scouting', 'EQUIPO', 'Claves', 'Zonas', 'Cuartos', 'Comparativa', 'LF Challenge', 'Pag.']) expect(text).toContain(word)
    for (const c of vectors.cases) {
      expect((await scoutingPdf(c.report as unknown as ScoutingReport, { ownName: c.own_name })).size).toBeGreaterThan(1000)
    }
  })
})
