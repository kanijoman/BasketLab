import { describe, expect, it } from 'vitest'
import { reportBlocks, type Block } from './blocks'
import { renderPdf } from './pdf'
import type { PostMatchReport } from '../engine/types'

const text = (bytes: Uint8Array) => new TextDecoder('latin1').decode(bytes)
const pages = (bytes: Uint8Array) => (text(bytes).match(/\/Type\s*\/Page\b/g) ?? []).length

const BLOCKS: Block[] = [
  { kind: 'title', text: 'MIPELLETYMAS B.F. LEON – RECOLETAS ZAMORA', sub: 'Derrota 38-59 · Informe post-partido' },
  { kind: 'heading', text: 'Resumen por cuartos' },
  { kind: 'table', head: ['Cuarto', 'Propio', 'Rival', 'Neto'], rows: [['Cuarto 1', '10', '12', '-2']] },
  { kind: 'chart', points: [[0, 0], [60, 2], [120, -3], [2400, -21]] },
  { kind: 'text', text: 'Q2 06:44 · Parcial en contra 0-9', bold: true },
  { kind: 'bullets', items: ['Pérdidas: 6 vs 3'] },
]

describe('renderPdf (issue #409)', () => {
  it('produces a PDF whose text can be read back (uncompressed)', async () => {
    const bytes = await renderPdf(BLOCKS, { compress: false })
    expect(text(bytes).startsWith('%PDF-')).toBe(true)
    expect(text(bytes)).toContain('RECOLETAS ZAMORA')
    expect(text(bytes)).toContain('Parcial en contra 0-9')
    expect(pages(bytes)).toBe(1)
  })

  it('is smaller when compressed, which is how the app shares it', async () => {
    const plain = await renderPdf(BLOCKS, { compress: false })
    const packed = await renderPdf(BLOCKS)
    expect(packed.length).toBeLessThan(plain.length)
  })

  it('flows onto more pages when the content is long, with no row cut in the middle', async () => {
    const rows = Array.from({ length: 120 }, (_, i) => [`Q${(i % 4) + 1} 0${i % 10}:00`, '10-12', 'Aviso', 'faltas', `Alerta número ${i} con un texto bastante largo para que ocupe más de una línea en la tabla del anexo`])
    const long: Block[] = [...BLOCKS, { kind: 'table', head: ['Reloj', 'Marcador', 'Nivel', 'Tipo', 'Alerta'], rows, widths: [0.12, 0.1, 0.09, 0.12, 0.57] }]
    const bytes = await renderPdf(long, { compress: false })
    expect(pages(bytes)).toBeGreaterThan(2)
    expect(text(bytes)).toContain('Alerta número 119')
  })

  it('numbers the pages in the footer', async () => {
    const long: Block[] = [...BLOCKS, ...Array.from({ length: 80 }, (): Block => ({ kind: 'text', text: 'Línea de relleno para forzar otra página del informe' }))]
    const bytes = await renderPdf(long, { compress: false })
    expect(text(bytes)).toMatch(/Página 2 de \d/)
  })

  it('keeps a text with a character the font lacks readable instead of spacing every letter out (issue #423)', async () => {
    const message = 'Entra M. MANSILLA por S. CASTRO (cede algo en el acierto de tiro: -0.3 σ). Rol similar (distancia 2.1)'
    const bytes = await renderPdf([{ kind: 'text', text: message }, { kind: 'table', head: ['Alerta'], rows: [[message]] }], { compress: false })
    expect(text(bytes)).toContain('acierto de tiro: -0.3 desv.')
    expect(text(bytes)).not.toContain('σ')
  })

  it('renders the report of a whole match', async () => {
    const empty = { match: { own: { id: '1', name: 'A' }, rival: { id: '2', name: 'B' }, home_id: null, score: { own: 1, rival: 0 }, result: 'win', periods: [] },
      evolution: { lead_changes: 0, ties: 0, max_lead: { margin: 0, elapsed: 0 }, max_deficit: { margin: 0, elapsed: 0 }, timeline: [[0, 0], [60, 0]], narrative: [] },
      runs: [], lineups: { best: [], worst: [] }, players: { top: [], bottom: [] },
      four_factors: { own: { efg: 0, tov: 0, orb: 0, ftr: 0 }, rival: { efg: 0, tov: 0, orb: 0, ftr: 0 } },
      team: { own: { possessions: 0, rating: 0, factors: { efg: 0, tov: 0, orb: 0, ftr: 0 }, stats: {} }, rival: { possessions: 0, rating: 0, factors: { efg: 0, tov: 0, orb: 0, ftr: 0 }, stats: {} } },
      went_well: [], to_improve: [], alerts: [], timeline: [], version: 1 } as unknown as PostMatchReport
    const bytes = await renderPdf(reportBlocks(empty))
    expect(text(bytes).startsWith('%PDF-')).toBe(true)
  })
})
