// The PDF of the rival scouting, made in the browser (issue #715). The server lays the report out with fpdf2 (`services/scouting_pdf.py`): headings, paragraphs, bullets, tables with their
// widths and coloured cells, spacing and a zones chart. `scoutingCalls` asks for exactly what that layout asks (call by call, same order and texts; `tests/local_vectors/scouting_pdf.json`
// records the real layout over a recorder) and `scoutingPdf` draws those calls with jsPDF, loaded when the button is pressed. The report is the sealed one (or the job's JSON).
import type { ScoutingReport } from '@/api/scoutingRival'
import { pyFixed } from '@/localdata/pyMath'

type Color = [number, number, number]
const DARK: Color = [30, 30, 30]
const ACCENT: Color = [50, 50, 80]
const SOFT: Color = [240, 240, 245]
const GREEN: Color = [30, 130, 70]
const RED: Color = [180, 40, 40]
const MUTED: Color = [110, 110, 120]

export type Call =
  | ['h1', string]
  | ['h2', string, number]
  | ['para', string, number, boolean, Color]
  | ['bullet', string, string, number]
  | ['ln', number | null]
  | ['image', number]
  | ['table', string[], Array<Array<string | number>>, number[], string[] | null, Array<Array<Color | null>> | null]

/** What the report has beyond the typed fields: the quarters, the edges, the timeouts and the zones of the shots. */
interface ZoneRow { label: string; own_fga: number; own_fg_pct: number | null; league_fg_pct: number | null; own_delta_pp: number | null; conceded_fga: number; conceded_fg_pct: number | null; conceded_delta_pp: number | null }
interface Extras {
  zones?: ZoneRow[]
  quarters?: Record<string, { for: number; against: number; margin: number }>
  edges?: { start?: Record<string, number>; close?: Record<string, number> }
  timeouts?: { per_game?: number; first_half: number; second_half: number; after_for: number; after_against: number }
}
type Full = ScoutingReport & Extras

const AREA_TAG: Record<string, string> = { ataque: '[Ataque]', defensa: '[Defensa]', jugadoras: '[Jugadores]', ritmo: '[Ritmo]', cierres: '[Cierres]', 'gestión': '[Gestión]' }
const COMPARISON_ROWS = 14

/** Spanish number (`fmt` of the report): decimal comma, no real minus sign. */
const fmt = (value: number, digits = 1, sign = false): string => pyFixed(value, digits, sign).replace('.', ',')
const pct = (value: number | null | undefined, sign = false): string => (value === null || value === undefined ? '-' : `${fmt(value, 0, sign)} %`)

function deltaColor(delta: number | null | undefined, goodHigh: boolean): Color | null {
  if (delta === null || delta === undefined || Math.abs(delta) < 4) return null
  return (delta > 0) === goodHigh ? GREEN : RED
}

/** Does the zones chart exist? (the server draws one when some of the first ten zones has a percentage). */
const hasChart = (zones: ZoneRow[]): boolean => zones.slice(0, 10).some(z => z.own_fg_pct !== null || z.conceded_fg_pct !== null)

/** The layout of the server, as the calls it makes (`scouting_pdf.lay_out`). */
export function scoutingCalls(report: ScoutingReport, ownName = 'Nuestro equipo'): Call[] {
  const r = report as Full
  const calls: Call[] = []
  const team = r.team.name
  const female = r.gender === 'F'
  const para = (text: string, size = 10, bold = false, color: Color = DARK) => calls.push(['para', text, size, bold, color])
  const bullet = (text: string, tag = '', size = 10) => calls.push(['bullet', text, tag, size])
  const h2 = (text: string, keepWith = 35) => calls.push(['h2', text, keepWith])
  const table = (headers: string[], rows: Array<Array<string | number>>, widths: number[], aligns: string[] | null = null, colors: Array<Array<Color | null>> | null = null) =>
    calls.push(['table', headers, rows, widths, aligns, colors])

  // summary
  calls.push(['h1', team])
  para(`${r.sample_games} partidos analizados con el motor del directo | Balance ${r.record.wins}-${r.record.losses} | ${fmt(r.record.avg_for)} a favor, ${fmt(r.record.avg_against)} en contra (${fmt(r.record.avg_margin, 1, true)} de media)`, 9, false, MUTED)
  for (const notice of r.notices) { calls.push(['ln', 1]); para(notice, 9, true, RED) }
  if (r.profile.length > 0) { h2('Perfil'); r.profile.forEach(line => bullet(line)) }

  // keys and plan
  if (r.keys.length > 0) {
    h2('Claves tácticas')
    for (const key of r.keys) {
      const tag = AREA_TAG[key.area] ?? `[${key.area}]`
      bullet(key.text, female ? tag.replace('Jugadores', 'Jugadoras') : tag)
    }
  }
  if (r.plan.neutralize.length > 0 || r.plan.exploit.length > 0) {
    h2('Plan de partido')
    for (const [title, plan] of [['Peligros a neutralizar', r.plan.neutralize], ['Debilidades a explotar', r.plan.exploit]] as const) {
      if (plan.length > 0) { para(title, 10, true, title.startsWith('Deb') ? GREEN : RED); plan.forEach(item => bullet(item.text)) }
    }
  }

  // people
  if (r.players.length > 0) {
    h2(female ? 'Jugadoras clave' : 'Jugadores clave')
    table([female ? 'Jugadora' : 'Jugador', 'PJ', 'Min/p', 'Pts/p', '% puntos', 'Pts cierre', 'TC cierre'],
      r.players.map(p => [p.name, p.games, fmt(p.minutes / p.games), fmt(p.pts_per_game), `${pyFixed(p.share * 100, 0)} %`, p.clutch.pts, p.clutch.fga]), [62, 14, 20, 20, 24, 24, 22])
  }
  if (r.lineups.length > 0) { h2('Quintetos más usados'); r.lineups.slice(0, 5).forEach(line => bullet(line.text)) }

  // zones
  const zones = r.zones ?? []
  if (zones.length > 0) {
    const chart = hasChart(zones)
    h2('Zonas de tiro', chart ? 120 : 35)
    if (chart) calls.push(['image', 175])
    table(['Zona', 'Tiros', '% propio', '% liga', 'Dif.', 'Concede', '% concede', 'Dif.'],
      zones.map(z => [z.label, z.own_fga, pct(z.own_fg_pct), pct(z.league_fg_pct), pct(z.own_delta_pp, true), z.conceded_fga, pct(z.conceded_fg_pct), pct(z.conceded_delta_pp, true)]),
      [38, 16, 22, 20, 18, 20, 24, 18], null, zones.map(z => [null, null, null, null, deltaColor(z.own_delta_pp, true), null, null, deltaColor(z.conceded_delta_pp, false)]))
  }

  // patterns
  const quarters = r.quarters ?? {}
  if (Object.keys(quarters).length > 0) {
    h2('Cuartos')
    table(['', 'A favor', 'En contra', 'Margen', "Inicio (3')", "Cierre (3')"],
      Object.keys(quarters).sort().map(p => {
        const q = quarters[p]
        return [`Cuarto ${p}`, fmt(q.for), fmt(q.against), fmt(q.margin, 1, true), fmt(r.edges?.start?.[p] ?? 0.0, 1, true), fmt(r.edges?.close?.[p] ?? 0.0, 1, true)]
      }), [34, 28, 28, 28, 32, 32])
  }
  const timeouts = r.timeouts
  if (timeouts && timeouts.per_game) {
    calls.push(['ln', 2])
    para(`Tiempos muertos: ${fmt(timeouts.per_game)} por partido (${fmt(timeouts.first_half)} en la 1.a parte, ${fmt(timeouts.second_half)} en la 2.a). `
      + `En los 2 minutos siguientes anotan ${fmt(timeouts.after_for)} y reciben ${fmt(timeouts.after_against)} de media.`, 9)
  }

  // origin of the points
  const origin = r.origin ?? []
  if (origin.length > 0) {
    h2('Origen de los puntos')
    para('Por partido; definición por posesión (la de la FEB es más estricta). «Concede» = lo que anotan sus rivales.', 8, false, MUTED)
    const cell = (value: number | null, key: string) => (value === null ? '-' : fmt(value, 1) + (key === 'bench_pct' ? ' %' : ''))
    table(['', 'Propio', 'Liga', 'Dif.', 'Concede', 'Dif.'],
      origin.map(o => [o.label, cell(o.own, o.key), cell(o.league, o.key), pct(o.own_delta_pct, true), cell(o.conceded, o.key), pct(o.conceded_delta_pct, true)]),
      [60, 24, 24, 22, 28, 22], null, origin.map(o => [null, null, null, deltaColor(o.own_delta_pct, true), null, deltaColor(o.conceded_delta_pct, false)]))
  }

  // alerts and matchup
  if (r.alerts.length > 0) {
    h2('Alertas del motor sobre este equipo')
    para('Lo que el motor del directo avisaría en sus partidos (por partido y minuto medio).', 8, false, MUTED)
    r.alerts.forEach(alert => bullet(alert.text, '', 9))
  }
  if (r.comparison.length > 0) {
    h2(`Comparativa: ${ownName} frente a ${team}`)
    const shown = r.comparison.filter(c => c.advantage !== 'neutral').slice(0, COMPARISON_ROWS)
    const winner = { own: ownName, rival: team, even: 'Igualado' }
    table(['Estadística', ownName, team, 'Ventaja'], shown.map(c => [c.label, c.own_text, c.rival_text, winner[c.advantage as 'own' | 'rival' | 'even']]), [66, 32, 32, 56], ['L', 'R', 'R', 'L'],
      shown.map(c => [null, null, null, c.advantage === 'own' ? GREEN : c.advantage === 'rival' ? RED : null]))
  }

  // games
  h2('Partidos analizados')
  table(['Fecha', 'Rival', 'Cancha', 'Resultado', ''], r.games.map(g => [g.date.slice(0, 10), g.opponent, g.home ? 'Local' : 'Visitante', `${g.score_for}-${g.score_against}`, g.margin > 0 ? 'V' : 'D']),
    [26, 84, 26, 30, 10], ['L', 'L', 'L', 'R', 'C'])
  return calls
}

// -- the page ---------------------------------------------------------------------------------------------------------

const TYPOGRAPHY: Record<number, string> = { 0x201c: '"', 0x201d: '"', 0x2018: "'", 0x2019: "'", 0x2013: '-', 0x2014: '-', 0x2026: '...', 0x2192: '->', 0x2212: '-' }

/** A string the standard fonts can write (`safe` of the server): typographic marks made plain, and each character beyond Latin-1 (an emoji is one) a question mark. */
export function scoutingSafe(text: unknown): string {
  return Array.from(String(text)).map(ch => {
    const code = ch.codePointAt(0) as number
    return TYPOGRAPHY[code] ?? (code > 0xff ? '?' : ch)
  }).join('')
}

const POINT = 0.3528
const MARGIN = 12
const BOTTOM = 16

interface Doc {
  setFont(name: string, style?: string): unknown
  setFontSize(size: number): unknown
  setTextColor(r: number, g: number, b: number): unknown
  setFillColor(r: number, g: number, b: number): unknown
  setDrawColor(r: number, g: number, b: number): unknown
  setLineWidth(width: number): unknown
  rect(x: number, y: number, w: number, h: number, style?: string): unknown
  line(x1: number, y1: number, x2: number, y2: number): unknown
  text(text: string, x: number, y: number, options?: { align?: string }): unknown
  getTextWidth(text: string): number
  splitTextToSize(text: string, width: number): string[]
  addPage(): unknown
  getNumberOfPages(): number
  setPage(page: number): unknown
  internal: { pageSize: { getHeight(): number; getWidth(): number } }
  output(type: 'arraybuffer'): ArrayBuffer
}

/** The report as a PDF: the page frame, the calls of the layout and the zones chart drawn with rectangles. */
export async function scoutingPdf(report: ScoutingReport, options: { subtitle?: string; ownName?: string; compress?: boolean } = {}): Promise<Blob> {
  const { jsPDF } = await import('jspdf')
  const pdf = new jsPDF({ unit: 'mm', format: 'a4', compress: options.compress ?? true }) as unknown as Doc
  const height = pdf.internal.pageSize.getHeight()
  const full = report as Full
  let y = 18

  const newPage = () => { pdf.addPage(); y = 18 }
  const ensure = (needed: number) => { if (y + needed > height - BOTTOM) newPage() }
  const text = (value: string, x: number, size: number, bold = false, color: Color = DARK, align?: 'center' | 'right') => {
    pdf.setFont('helvetica', bold ? 'bold' : 'normal'); pdf.setFontSize(size); pdf.setTextColor(...color)
    pdf.text(scoutingSafe(value), x, y + size * POINT, align ? { align } : undefined)
  }
  const wrapped = (value: string, x: number, width: number, size: number, bold: boolean, color: Color, lineHeight: number) => {
    pdf.setFont('helvetica', bold ? 'bold' : 'normal'); pdf.setFontSize(size)
    for (const line of pdf.splitTextToSize(scoutingSafe(value), width)) {
      ensure(lineHeight)
      text(line, x, size, bold, color)
      y += lineHeight
    }
  }

  const chart = (width: number) => {
    const shown = (full.zones ?? []).filter(z => z.own_fg_pct !== null || z.conceded_fg_pct !== null).slice(0, 10)
    const total = (width * (0.45 * shown.length + 1.1)) / 7.2
    ensure(total)
    const label = 38
    const plot = width - label - 4
    const bar = (total - 14) / shown.length
    shown.forEach((z, i) => {
      const top = y + 2 + i * bar
      pdf.setFont('helvetica', 'normal'); pdf.setFontSize(7); pdf.setTextColor(...DARK)
      pdf.text(scoutingSafe(`${z.label} (${z.own_fga})`), MARGIN, top + bar * 0.6)
      pdf.setFillColor(0x3b, 0x5b, 0x92); pdf.rect(MARGIN + label, top + bar * 0.08, (plot * (z.own_fg_pct ?? 0)) / 100, bar * 0.38, 'F')
      pdf.setFillColor(0xd9, 0x8c, 0x3d); pdf.rect(MARGIN + label, top + bar * 0.5, (plot * (z.conceded_fg_pct ?? 0)) / 100, bar * 0.38, 'F')
      if (z.league_fg_pct !== null) { pdf.setDrawColor(0, 0, 0); pdf.setLineWidth(0.5); pdf.line(MARGIN + label + (plot * z.league_fg_pct) / 100, top, MARGIN + label + (plot * z.league_fg_pct) / 100, top + bar) }
    })
    const legend = y + total - 9
    pdf.setFillColor(0x3b, 0x5b, 0x92); pdf.rect(MARGIN + label, legend, 3, 3, 'F'); text(`${full.team.name}: tiros propios`, MARGIN + label + 5, 7)
    y = legend
    pdf.setFillColor(0xd9, 0x8c, 0x3d); pdf.rect(MARGIN + label, legend + 4, 3, 3, 'F'); y = legend + 4; text('Tiros que concede', MARGIN + label + 5, 7)
    y = legend + 9
  }

  const drawTable = (headers: string[], rows: Array<Array<string | number>>, widths: number[], aligns: string[] | null, colors: Array<Array<Color | null>> | null) => {
    const al = aligns ?? ['L', ...Array(headers.length - 1).fill('R')]
    const cell = (value: string, x: number, w: number, align: string, size: number, bold: boolean, color: Color, fill: Color) => {
      pdf.setFillColor(...fill); pdf.setDrawColor(150, 150, 150); pdf.setLineWidth(0.2); pdf.rect(x, y, w, 5.5, 'FD')
      pdf.setFont('helvetica', bold ? 'bold' : 'normal'); pdf.setFontSize(size)
      let shown = scoutingSafe(value)
      while (shown && pdf.getTextWidth(shown) > w - 2) shown = shown.slice(0, -1)
      const at = align === 'R' ? x + w - 1 : align === 'C' ? x + w / 2 : x + 1
      pdf.setTextColor(...color)
      pdf.text(shown, at, y + 3.9, align === 'R' ? { align: 'right' } : align === 'C' ? { align: 'center' } : undefined)
    }
    ensure(6)
    let x = MARGIN
    headers.forEach((head, j) => { cell(head, x, widths[j], al[j], 8.5, true, [255, 255, 255], ACCENT); x += widths[j] })
    y += 6
    rows.forEach((row, i) => {
      if (y > 270) newPage()
      x = MARGIN
      row.forEach((value, j) => { cell(String(value), x, widths[j], al[j], 8.5, false, colors?.[i]?.[j] ?? DARK, i % 2 ? SOFT : [255, 255, 255]); x += widths[j] })
      y += 5.5
    })
  }

  for (const call of scoutingCalls(report, options.ownName ?? 'Nuestro equipo')) {
    switch (call[0]) {
      case 'h1': wrapped(call[1], MARGIN, 186, 18, true, DARK, 9); break
      case 'h2': {
        ensure(call[2]); y += 3
        pdf.setFillColor(...ACCENT); pdf.rect(MARGIN, y, 186, 7, 'F')
        text(` ${call[1]}`, MARGIN, 11, true, [255, 255, 255]); y += 7 + 1.5 - 0.0; y += 0
        break
      }
      case 'para': wrapped(call[1], MARGIN, 186, call[2], call[3], call[4], 5); break
      case 'bullet': {
        ensure(5.8); text('-', 14, call[3], true)
        const tag = call[2] ? scoutingSafe(call[2]) : ''
        pdf.setFont('helvetica', 'bold'); pdf.setFontSize(call[3])
        const offset = tag ? pdf.getTextWidth(tag) + 3 : 0
        if (tag) text(tag, 18, call[3], true, ACCENT)
        wrapped(call[1], 18 + offset, 186 - 6 - offset, call[3], false, DARK, 5)
        y += 0.8
        break
      }
      case 'ln': y += call[1] ?? 5; break
      case 'image': chart(call[1]); y += 2; break
      case 'table': drawTable(call[1], call[2], call[3], call[4], call[5]); break
    }
  }

  const pages = pdf.getNumberOfPages()
  const stamp = new Date().toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' })
  for (let page = 1; page <= pages; page++) {
    pdf.setPage(page)
    pdf.setFillColor(...DARK); pdf.rect(0, 0, 210, 14, 'F')
    y = 3; text('Scouting rival', MARGIN, 11, true, [255, 255, 255])
    y = height - 12
    text(`BasketLab | ${options.subtitle ? `${options.subtitle} | ` : ''}Generado el ${stamp} | Pag. ${page}`, 105, 8, false, MUTED, 'center')
  }
  return new Blob([pdf.output('arraybuffer')], { type: 'application/pdf' })
}
