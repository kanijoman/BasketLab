/** The post-match report as a list of layout blocks (issue #409). The PDF renderer only knows blocks; this file knows the football:
 *  what goes in which section, in Spanish, in a reading order for the technical staff. */
import type { PostMatchReport, ReportAlert, ReportLineup, ReportRun } from '../engine/types'

export type Block =
  | { kind: 'title'; text: string; sub: string }
  | { kind: 'heading'; text: string }
  | { kind: 'text'; text: string; bold?: boolean }
  | { kind: 'bullets'; items: string[] }
  | { kind: 'table'; head: string[]; rows: string[][]; widths?: number[] }
  | { kind: 'chart'; points: [number, number][] }

const RESULT: Record<PostMatchReport['match']['result'], string> = { win: 'Victoria', loss: 'Derrota', tie: 'Empate' }
const SEVERITY = { critical: 'Crítica', warning: 'Aviso', info: 'Info' }
const FACTOR_ROWS: [keyof PostMatchReport['four_factors']['own'], string][] = [
  ['efg', 'Acierto de tiro (eFG %)'], ['tov', 'Pérdidas (TOV %)'], ['orb', 'Rebote ofensivo (ORB %)'], ['ftr', 'Tiros libres (FTr)'],
]

// the PDF fonts print Latin-1: what is outside is replaced by something that reads the same
const REPLACEMENTS: [RegExp, string][] = [
  [/≥/g, '>='], [/≤/g, '<='], [/→/g, '->'], [/[“”]/g, '"'], [/[‘’]/g, "'"], [/…/g, '...'], [/[−]/g, '-'],
]

/** ``text`` with what the PDF font cannot print replaced; the accents of Spanish are kept. */
export function safeText(text: string): string {
  return REPLACEMENTS.reduce((acc, [pattern, to]) => acc.replace(pattern, to), text)
}

const pct = (value: number) => `${(value * 100).toFixed(0)} %`
const join = (items: string[]) => items.join(', ')
const signed = (value: number) => (value > 0 ? `+${value}` : String(value))

function lineupRows(rows: ReportLineup[]): string[][] {
  return rows.map(r => [join(r.players), `${Math.floor(r.seconds / 60)} min`, `${r.pts_for}-${r.pts_against}`, signed(r.net)])
}

function runBlocks(runs: ReportRun[]): Block[] {
  if (runs.length === 0) return [{ kind: 'bullets', items: ['Sin parciales de 8 o más puntos.'] }]
  return [...runs].sort((a, b) => a.start - b.start).flatMap((run): Block[] => {
    const mine = run.team === 'own'
    const score = mine ? `${run.pts}-${run.against}` : `${run.against}-${run.pts}`
    const title = `${run.clock} · ${mine ? 'Parcial a favor' : 'Parcial en contra'} ${score} (${run.score_before.join('-')} → ${run.score_after.join('-')})`
    return [
      { kind: 'text', text: title, bold: true },
      { kind: 'text', text: `En pista: ${join(run.lineup)}.` },
      { kind: 'text', text: run.explanation },
    ]
  })
}

function alertRows(alerts: ReportAlert[]): string[][] {
  return alerts.map(a => [
    a.period === null || a.clock === null ? '—' : `${a.period > 4 ? `PR${a.period - 4}` : `Q${a.period}`} ${a.clock}`,
    a.score ? `${a.score[0]}-${a.score[1]}` : '—', SEVERITY[a.severity] ?? a.severity, a.category,
    a.proposal.length ? `${a.message} Qué hacer: ${a.proposal.join('; ')}.` : a.message,
  ])
}

export function reportBlocks(report: PostMatchReport): Block[] {
  const { match, evolution, players, four_factors: ff, team } = report
  const periodNotes = match.periods.filter(p => p.keys.length || p.pace_text)
    .map(p => [p.keys.length ? `${p.label}: ${join(p.keys)}. Ajustes: ${join(p.adjustments)}.` : `${p.label}: sin claves destacadas.`, p.pace_text].filter(Boolean).join(' '))
  const blocks: Block[] = [
    { kind: 'title', text: `${match.own.name.trim()} – ${match.rival.name.trim()}`,
      sub: `${RESULT[match.result]} ${match.score.own}-${match.score.rival} · Informe post-partido` },
    { kind: 'heading', text: 'Resumen por cuartos' },
    { kind: 'table', head: ['Cuarto', 'Propio', 'Rival', 'Neto'], rows: match.periods.map(p => [p.label, String(p.own), String(p.rival), signed(p.net)]) },
    { kind: 'bullets', items: periodNotes.length ? periodNotes : ['Sin claves destacadas en ningún cuarto.'] },
    { kind: 'heading', text: 'Evolución del partido' },
    { kind: 'chart', points: evolution.timeline },
    { kind: 'bullets', items: evolution.narrative },
    { kind: 'heading', text: 'Parciales y por qué se produjeron' },
    ...runBlocks(report.runs),
    { kind: 'heading', text: 'Quintetos' },
    { kind: 'text', text: 'Mejores (más de 2 minutos juntos):', bold: true },
    { kind: 'table', head: ['Quinteto', 'Tiempo', 'Puntos', '+/-'], rows: lineupRows(report.lineups.best), widths: [0.6, 0.12, 0.14, 0.14] },
    { kind: 'text', text: 'Peores:', bold: true },
    { kind: 'table', head: ['Quinteto', 'Tiempo', 'Puntos', '+/-'], rows: lineupRows(report.lineups.worst), widths: [0.6, 0.12, 0.14, 0.14] },
    { kind: 'heading', text: 'Jugadoras (+/-)' },
    { kind: 'table', head: ['Jugadora', '+/-', 'Puntos', 'Minutos'],
      rows: [...players.top, ...players.bottom].map(p => [p.name, signed(p.pm), String(p.pts), String(Math.round(p.minutes / 60))]) },
    { kind: 'heading', text: 'Four Factors' },
    { kind: 'table', head: ['Factor', 'Propio', 'Rival'], rows: FACTOR_ROWS.map(([key, label]) => [label, pct(ff.own[key]), pct(ff.rival[key])]) },
    { kind: 'text', text: `Posesiones: ${team.own.possessions.toFixed(0)} y ${team.rival.possessions.toFixed(0)}. Rating: ${team.own.rating.toFixed(0)} frente a ${team.rival.rating.toFixed(0)} puntos por 100 posesiones.` },
    { kind: 'heading', text: 'Lo que ha ido bien' },
    { kind: 'bullets', items: report.went_well.length ? report.went_well : ['Sin aspectos destacados.'] },
    { kind: 'heading', text: 'Lo que podemos mejorar' },
    { kind: 'bullets', items: report.to_improve.length ? report.to_improve : ['Sin aspectos a mejorar destacados.'] },
    { kind: 'heading', text: 'Anexo: alertas del partido' },
  ]
  blocks.push(report.alerts.length
    ? { kind: 'table', head: ['Reloj', 'Marcador', 'Nivel', 'Tipo', 'Alerta'], rows: alertRows(report.alerts), widths: [0.12, 0.1, 0.09, 0.12, 0.57] }
    : { kind: 'bullets', items: ['Sin alertas registradas en este dispositivo para este partido.'] })
  return blocks
}
