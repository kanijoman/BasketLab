// The PDF of the team report, made in the browser (issue #714). The server wrote the report as HTML (`render_report_html`) and turned it into a PDF with fpdf2; this writes the very same
// HTML (`renderReportHtml`, string for string against `tests/local_vectors/report_html.json`), reads it into blocks (`htmlToBlocks`: headings, paragraphs and list items, with bold runs)
// and draws them with jsPDF (loaded when the button is pressed). The text goes through the same replacements as the server's, since the standard fonts of a PDF are Latin-1 only.
import type { ReportAction, ReportConsistency, ReportDifferential, ReportFinding, ReportZone, TeamReport } from '@/api/teamReport'
import { pyFixed } from '@/localdata/pyMath'

type Titles = { h1: string; strengths: string; weaknesses: string; tactics: string; training: string; training_intro: string }

const TITLES: Record<'own' | 'rival', Titles> = {
  own: {
    h1: 'Análisis de equipo', strengths: 'Puntos fuertes clave', weaknesses: 'Debilidades críticas', tactics: 'Recomendaciones tácticas', training: 'Enfoque de entrenamiento',
    training_intro: 'Prioridades de mejora, de mayor a menor diferencia con la liga:',
  },
  rival: {
    h1: 'Scouting rival', strengths: 'Peligros a neutralizar', weaknesses: 'Debilidades a explotar', tactics: 'Claves tácticas del partido', training: 'Plan de partido',
    training_intro: 'Acciones prioritarias: neutralizar sus fortalezas y explotar sus debilidades:',
  },
}
const KIND: Record<ReportAction['kind'], string> = { improve: 'Mejorar', leverage: 'Potenciar', neutralize: 'Neutralizar', exploit: 'Explotar' }

/** Python's `html.escape` (quotes too). */
const escape = (text: string): string => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;')

const items = (rows: string[]): string => (rows.length > 0 ? `<ul>${rows.map(r => `<li>${r}</li>`).join('')}</ul>` : '<p>Sin datos destacados.</p>')

function finding(f: ReportFinding): string {
  const diff = f.diff_pct !== null && f.diff_pct !== undefined ? ` (${pyFixed(f.diff_pct, 1, true)}% vs mediana de la liga)` : ''
  return `<b>${escape(f.label)}</b>: ${escape(f.formatted)}${diff}. ${escape(f.text)}`
}

const differential = (x: ReportDifferential): string =>
  `<b>[${x.advantage ? 'VENTAJA' : 'DESVENTAJA'}]</b> ${escape(x.label)}: ${escape(x.formatted)} (${pyFixed(x.diff_pct, 1, true)}% vs mediana)`

const consistency = (x: ReportConsistency): string =>
  `<b>[${x.status === 'inconsistent' ? 'INCONSISTENTE' : 'CONSISTENTE'}]</b> ${escape(x.label)} (CV ${pyFixed(x.cv, 0)}%). ${escape(x.text)}`

function zone(z: ReportZone): string {
  const note = z.low_sample ? ' (muestra pequeña)' : ''
  return `<b>[${z.kind === 'hot' ? 'CALIENTE' : 'FRIA'}]</b> ${escape(String(z.label))}: ${pyFixed(z.fg_pct ?? NaN, 0)}% en ${z.fga} tiros, liga ${pyFixed(z.league_pct ?? NaN, 0)}% (${pyFixed(z.delta_pp ?? NaN, 1, true)} pp)${note}. ${escape(z.text)}`
}

const action = (x: ReportAction): string => `<b>${KIND[x.kind]}</b> - ${escape(x.label)}: ${escape(x.text)}`

function tactics(rows: ReportAction[]): string {
  const out: string[] = []
  for (const area of ['ofensiva', 'defensiva'] as const) {
    const selected = rows.filter(x => x.area === area).map(action)
    if (selected.length > 0) out.push(`<h3>${area.charAt(0).toUpperCase()}${area.slice(1)}</h3>${items(selected)}`)
  }
  return out.join('') || '<p>Sin recomendaciones destacadas.</p>'
}

/** `render_report_html`: the report as the simple HTML the server turned into a PDF. */
export function renderReportHtml(report: TeamReport): string {
  const t = TITLES[report.mode]
  const parts = [
    `<h1>${t.h1}: ${escape(report.team)}</h1>`,
    `<p>Partidos analizados: ${report.games_played}. Comparado con los cuartiles de la competición.</p>`,
    report.low_sample ? `<p><b>Aviso: muestra pequeña (${report.games_played} partidos).</b> Los resultados son orientativos y pueden cambiar mucho en las próximas jornadas.</p>` : '',
    `<h2>Perfil de equipo</h2>${items(report.profile.map(escape))}`,
    `<h2>${t.strengths}</h2>${items(report.strengths.map(finding))}`,
    `<h2>${t.weaknesses}</h2>${items(report.weaknesses.map(finding))}`,
    `<h2>Análisis diferencial vs liga</h2>${items(report.differentials.map(differential))}`,
    `<h2>Zonas de tiro</h2>${items((report.zones ?? []).map(zone))}`,
    `<h2>Consistencia partido a partido</h2>${items(report.consistency.map(consistency))}`,
    `<h2>${t.tactics}</h2>${tactics(report.tactics)}`,
    `<h2>${t.training}</h2><p>${t.training_intro}</p>`,
    report.training.length > 0 ? `<ol>${report.training.map(x => `<li>${action(x)}</li>`).join('')}</ol>` : '<p>Sin prioridades destacadas.</p>',
  ]
  return parts.join('\n')
}

// -- HTML -> blocks ---------------------------------------------------------------------------------------------------

export interface Run { text: string; bold: boolean }
export type Block = { kind: 'h1' | 'h2' | 'h3' | 'p'; runs: Run[] } | { kind: 'li'; marker: string; runs: Run[] }

/** What the standard fonts of a PDF cannot show, as the server's `_replace_emojis` wrote it; anything else beyond Latin-1 becomes a question mark. */
const REPLACEMENTS: Array<[string, string]> = [
  ['🔥', '[+]'], ['⚠️', '[-]'], ['✅', '[OK]'], ['❌', '[X]'], ['⚡', '[!]'], ['💪', '[+]'], ['👍', '[+]'], ['👎', '[-]'], ['📈', '[IMPROVE]'], ['📉', '[DECLINE]'], ['🎯', '[TARGET]'],
  ['🏀', '[TEAM]'], ['⚔️', '[VS]'], ['🛡️', '[DEF]'], ['⛹️', '[PLAYER]'], ['🥇', '[1st]'], ['🥈', '[2nd]'], ['🥉', '[3rd]'], ['✓', '[+]'], ['✔', '[+]'], ['✗', '[-]'], ['✘', '[-]'],
  ['○', '[ ]'], ['●', '[*]'], ['◆', '[*]'], ['◇', '[ ]'], ['→', '->'], ['←', '<-'], ['↑', '^'], ['↓', 'v'], ['↔', '<->'], ['⚠', '[!]'], ['ℹ️', '[i]'], ['ℹ', '[i]'], ['💡', '[*]'],
  ['🔔', '[!]'], ['📊', '[STATS]'], ['📋', '[PLAN]'], ['🎓', '[TRAIN]'], ['🏆', '[WIN]'], ['…', '...'], ['—', '-'], ['–', '-'], ['“', '"'], ['”', '"'], ['‘', "'"], ['’', "'"],
]
export function pdfSafe(text: string): string {
  let out = text
  for (const [from, to] of REPLACEMENTS) out = out.split(from).join(to)
  return out.replace(/[Ā-￿]/g, '?')            // beyond Latin-1 (an emoji is two surrogates: both go)
}

const ENTITIES: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'" }
const unescapeHtml = (text: string): string => text.replace(/&(?:amp|lt|gt|quot|#x27);/g, entity => ENTITIES[entity])

/** The blocks of the HTML the renderer writes (`h1`–`h3`, `p`, `ul`/`ol` with `li`, and `b` inside them); text between blocks is layout only. */
export function htmlToBlocks(html: string): Block[] {
  const blocks: Block[] = []
  const lists: Array<{ ordered: boolean; count: number }> = []
  let open: { kind: Block['kind']; marker?: string } | null = null
  let runs: Run[] = []
  let bold = false
  for (const token of html.matchAll(/<(\/?)(h1|h2|h3|p|ul|ol|li|b)>|([^<]+)/g)) {
    const [, closing, tag, text] = token
    if (text !== undefined) {
      if (open) runs.push({ text: pdfSafe(unescapeHtml(text)), bold })
    } else if (tag === 'b') {
      bold = closing === ''
    } else if (tag === 'ul' || tag === 'ol') {
      if (closing === '') lists.push({ ordered: tag === 'ol', count: 0 })
      else lists.pop()
    } else if (closing === '') {
      const list = lists[lists.length - 1]
      if (tag === 'li' && list) list.count += 1
      open = { kind: tag as Block['kind'], marker: tag === 'li' ? (list?.ordered ? `${list.count}.` : '-') : undefined }
      runs = []
    } else if (open) {
      blocks.push(open.kind === 'li' ? { kind: 'li', marker: open.marker ?? '-', runs } : { kind: open.kind as 'h1' | 'h2' | 'h3' | 'p', runs })
      open = null
    }
  }
  return blocks
}

// -- the PDF -----------------------------------------------------------------------------------------------------------

const MARGIN = { left: 18, right: 18, top: 18, bottom: 18 }
const POINT = 0.3528                                   // millimetres in a point
const STYLE: Record<Block['kind'], { size: number; bold: boolean; before: number; after: number }> = {
  h1: { size: 16, bold: true, before: 0, after: 4 }, h2: { size: 13, bold: true, before: 5, after: 2 }, h3: { size: 11, bold: true, before: 3, after: 1 },
  p: { size: 10, bold: false, before: 0, after: 2 }, li: { size: 10, bold: false, before: 0, after: 1 },
}

/** The report as a PDF. jsPDF is loaded here, when the button is pressed. */
export async function teamReportPdf(report: TeamReport, options: { compress?: boolean } = {}): Promise<Blob> {
  const { jsPDF } = await import('jspdf')
  const pdf = new jsPDF({ unit: 'mm', format: 'a4', compress: options.compress ?? true })
  const height = pdf.internal.pageSize.getHeight()
  const width = pdf.internal.pageSize.getWidth() - MARGIN.left - MARGIN.right
  let y = MARGIN.top

  const drawLine = (words: Run[], x: number, size: number, lineHeight: number) => {
    if (y + lineHeight > height - MARGIN.bottom) { pdf.addPage(); y = MARGIN.top }
    let cursor = x
    for (const word of words) {
      pdf.setFont('helvetica', word.bold ? 'bold' : 'normal')
      pdf.text(word.text, cursor, y + size * POINT)
      cursor += pdf.getTextWidth(`${word.text} `)
    }
    y += lineHeight
  }

  for (const block of htmlToBlocks(renderReportHtml(report))) {
    const style = STYLE[block.kind]
    const indent = block.kind === 'li' ? 6 : 0
    const lineHeight = style.size * POINT * 1.35
    pdf.setFontSize(style.size)
    y += style.before
    const words: Run[] = block.runs.flatMap(run => run.text.split(/\s+/).filter(Boolean).map(text => ({ text, bold: run.bold || style.bold })))
    if (block.kind === 'li') {
      pdf.setFont('helvetica', 'normal')
      if (y + lineHeight > height - MARGIN.bottom) { pdf.addPage(); y = MARGIN.top }
      pdf.text(block.marker, MARGIN.left, y + style.size * POINT)
    }
    let current: Run[] = []
    let used = 0
    for (const word of words) {
      pdf.setFont('helvetica', word.bold ? 'bold' : 'normal')
      const need = pdf.getTextWidth(`${word.text} `)
      if (used + need > width - indent && current.length > 0) {
        drawLine(current, MARGIN.left + indent, style.size, lineHeight)
        current = []
        used = 0
      }
      current.push(word)
      used += need
    }
    if (current.length > 0) drawLine(current, MARGIN.left + indent, style.size, lineHeight)
    y += style.after
  }
  return new Blob([pdf.output('arraybuffer')], { type: 'application/pdf' })
}
