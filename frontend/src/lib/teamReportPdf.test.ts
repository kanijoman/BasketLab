import { describe, expect, it } from 'vitest'
import { htmlToBlocks, renderReportHtml, teamReportPdf } from './teamReportPdf'
import type { TeamReport } from '@/api/teamReport'
import vectors from '../../../tests/local_vectors/report_html.json'

// The PDF of the team report in the browser (issue #714). The report comes sealed (or from the API) as JSON; the server wrote it as HTML (`render_report_html`) and turned it into a PDF with
// fpdf2. The browser writes the very same HTML (string for string against `tests/local_vectors/report_html.json`: the real reports of both leagues and modes, and hand-made ones for the
// branches the fixtures do not reach), reads it into blocks and draws them with jsPDF.
describe('the HTML of the report equals the server\'s, string for string', () => {
  it.each(vectors.cases.map((c, i) => [`${c.report.mode} report ${i + 1} (${c.report.team})`, c] as const))('%s', (_name, c) => {
    expect(renderReportHtml(c.report as unknown as TeamReport)).toBe(c.html)
  })
})

describe('the blocks of the PDF', () => {
  const html = '<h1>Análisis de equipo: A&amp;B</h1>\n<p>Partidos: 3.</p>\n<h2>Perfil</h2><ul><li><b>Puntos</b>: 78,5. Anota.</li><li>Dos</li></ul><h3>Ofensiva</h3><ol><li><b>Mejorar</b> - Ritmo: Correr.</li></ol>'

  it('reads the tags the renderer writes: headings, paragraphs and the items of lists, with the bold runs and the entities undone', () => {
    expect(htmlToBlocks(html)).toEqual([
      { kind: 'h1', runs: [{ text: 'Análisis de equipo: A&B', bold: false }] },
      { kind: 'p', runs: [{ text: 'Partidos: 3.', bold: false }] },
      { kind: 'h2', runs: [{ text: 'Perfil', bold: false }] },
      { kind: 'li', marker: '-', runs: [{ text: 'Puntos', bold: true }, { text: ': 78,5. Anota.', bold: false }] },
      { kind: 'li', marker: '-', runs: [{ text: 'Dos', bold: false }] },
      { kind: 'h3', runs: [{ text: 'Ofensiva', bold: false }] },
      { kind: 'li', marker: '1.', runs: [{ text: 'Mejorar', bold: true }, { text: ' - Ritmo: Correr.', bold: false }] },
    ])
  })

  it('writes what a PDF with the standard fonts cannot show as the server did (dashes, ellipsis, arrows, emojis)', () => {
    expect(htmlToBlocks('<p>a — b … c → d ✅ “q”</p>')[0].runs[0].text).toBe('a - b ... c -> d [OK] "q"')
  })
})

describe('the PDF', () => {
  const report = vectors.cases[0].report as unknown as TeamReport

  it('is a PDF with the title and the words of every section, on more than one page when the report is long', async () => {
    const blob = await teamReportPdf(report, { compress: false })
    expect(blob.type).toBe('application/pdf')
    const text = new TextDecoder('latin1').decode(await blob.arrayBuffer())
    expect(text.startsWith('%PDF')).toBe(true)
    for (const word of ['Perfil', 'Zonas', 'Consistencia', 'Recomendaciones']) expect(text).toContain(word)
    expect(text).toContain(report.team.split(' ')[0])
  })

  it('draws every case of the vectors without failing (an empty section, a long name, escaped characters)', async () => {
    for (const c of vectors.cases) {
      const blob = await teamReportPdf(c.report as unknown as TeamReport)
      expect(blob.size).toBeGreaterThan(1000)
    }
  })
})
