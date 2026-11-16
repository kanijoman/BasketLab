// What the export of the preview writes to its CSV (#849, #940): the objectives, what is information, the question of the card «¿Y si…?» (when there is one) and the scenarios.
import { conditionsTitle, infoLines, leverEvidence, leverTitle, pct, recordLines, SCENARIO_TEXT } from '@/forecast/copy'
import type { PreviewDetail } from '@/forecast/preview'
import type { ProjectionResult } from '@/forecast/projection/project'

export type CsvRow = { tipo: string; texto: string; victorias: string; temporada: string }

export const CSV_HEADERS = [{ key: 'tipo', label: 'Tipo' }, { key: 'texto', label: 'Qué' }, { key: 'victorias', label: 'Victorias' }, { key: 'temporada', label: 'Esta temporada' }]

export function previewCsv(detail: PreviewDetail, question: ProjectionResult | null, rivalName: string): CsvRow[] {
  const records = question && recordLines(question, rivalName)
  return [
    ...[...detail.levers.attack, ...detail.levers.defence].map(l => ({ tipo: 'Objetivo', texto: leverTitle(l), victorias: pct(l.pWin, 0), temporada: leverEvidence(l) })),
    ...detail.levers.info.map(i => { const lines = infoLines(i); return { tipo: lines.title, texto: lines.summary, victorias: '', temporada: lines.record } }),
    ...(question && records ? [{ tipo: 'Condición', texto: conditionsTitle(question.conditions), victorias: question.figure === null ? '' : pct(question.figure, 0), temporada: `${records.own} ${records.rival}` }] : []),
    ...detail.scenarios.map(b => ({ tipo: 'Escenario', texto: SCENARIO_TEXT[b.id].title, victorias: pct(b.p, 0), temporada: '' })),
  ]
}
