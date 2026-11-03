// The DOCX of the individual scouting made in the browser (issue #717, 17b): one page per player of the team (the rival of the week), as `IndividualScoutingDocxBuilder` wrote it on the server:
// header, identity (photo, date of birth, age, height), averages, totals and advanced tables shaded by quartile against the whole league, and a blank notes section.
// What the tables say is a port of `scouting_docx_tables.player_tables` (parity: `scoutingDocx.test.ts` against `tests/local_vectors/scouting_docx.json`); the library `docx` is loaded on demand.
import type { PlayerStat } from '@/api/client'
import type { TeamImages } from '@/webdata/client'
import { percentile } from '@/localdata/playerQuartiles'
import { pyFixed, pyRound } from '@/localdata/pyMath'

type Column = readonly [header: string, key: string, kind: 'min' | 'pct' | 'num', lowerIsBetter: boolean]

const AVERAGES: Column[] = [
  ['PJ', 'games_played', 'num', false], ['MIN', 'minutes_per_game', 'min', false], ['PTS', 'points_per_game', 'num', false],
  ['TL%', 'fg1_percentage', 'pct', false], ['T2%', 'fg2_percentage', 'pct', false], ['T3%', 'fg3_percentage', 'pct', false],
  ['RO', 'offensive_rebounds_per_game', 'num', false], ['RD', 'defensive_rebounds_per_game', 'num', false], ['RT', 'rebounds_per_game', 'num', false],
  ['AST', 'assists_per_game', 'num', false], ['ROB', 'steals_per_game', 'num', false], ['BP', 'turnovers_per_game', 'num', true],
  ['TAP', 'blocks_per_game', 'num', false], ['FP', 'fouls_per_game', 'num', true], ['VAL', 'valoracion_per_game', 'num', false],
]
const ADVANCED: Column[] = [
  ['TS%', 'true_shooting', 'pct', false], ['eFG%', 'efg_percentage', 'pct', false], ['3PAr', 'three_point_rate', 'pct', false], ['FTr', 'free_throw_rate', 'pct', false],
  ['ORB%', 'orb_pct', 'pct', false], ['DRB%', 'drb_pct', 'pct', false], ['AST%', 'ast_pct', 'pct', false], ['TO%', 'tov_pct_adv', 'pct', true],
  ['ROB%', 'stl_pct', 'pct', false], ['TAP%', 'blk_pct', 'pct', false], ['USG%', 'usage_pct', 'pct', false], ['ORtg', 'orating', 'num', false],
  ['DRtg', 'drating', 'num', true], ['NetRtg', 'net_rtg', 'num', false],
]
const TOTALS_HEADERS = AVERAGES.map(c => c[0])
const JOINER = '⁠/⁠'                                  // a word-joiner around the slash: Word does not break "10/14" there

export interface Cell { text: string; fill: string | null }
export interface PlayerTables {
  averages: { headers: string[]; cells: Cell[] }
  totals: { headers: string[]; cells: string[] }
  advanced: { headers: string[]; cells: Cell[] }
}

type Row = Record<string, unknown>

/** `safe` of `_scouting_formatters`: one decimal, `-` when there is no figure, the text itself when it is not a number. */
function safe(value: unknown, suffix = ''): string {
  if (value === null || value === undefined) return '-'
  const n = typeof value === 'string' ? (value.trim() === '' ? NaN : Number(value)) : Number(value)
  if (typeof value === 'string' && Number.isNaN(n)) return value
  if (Number.isNaN(n)) return `nan${suffix}`
  return Number.isFinite(n) ? pyFixed(n, 1) + suffix : `${n < 0 ? '-' : ''}inf${suffix}`
}

/** `fmt_min`: minutes as `M:SS` (the seconds as Python rounds them, so a figure just under a minute is `5:60`, as it always was). */
function minutes(value: unknown): string {
  if (value === null || value === undefined) return '-'
  const m = Number(value)
  if (Number.isNaN(m)) return String(value)
  return `${Math.trunc(m)}:${String(pyRound(((m % 1) + 1) % 1 * 60, 0)).padStart(2, '0')}`
}

/** `quartile_fill`: Q4 green, Q3 yellow, Q2 orange, Q1 red (reversed for the columns where less is better); no colour below four values or without a figure. */
function fill(value: unknown, league: unknown[], reverse: boolean): string | null {
  const values = league.filter(v => v !== null && v !== undefined).map(Number).sort((a, b) => a - b)
  if (values.length < 4 || value === null || value === undefined) return null
  const [q25, q50, q75] = [0.25, 0.5, 0.75].map(q => percentile(values, q))
  const v = Number(value)
  if (!reverse) return v >= q75 ? 'C6EFCE' : v >= q50 ? 'FFEB9C' : v >= q25 ? 'FFD9B3' : 'FFC7CE'
  return v <= q25 ? 'C6EFCE' : v <= q50 ? 'FFEB9C' : v <= q75 ? 'FFD9B3' : 'FFC7CE'
}

function coloured(player: Row, league: Row[], columns: Column[]) {
  return {
    headers: columns.map(c => c[0]),
    cells: columns.map(([, key, kind, lower]): Cell => ({
      text: kind === 'min' ? minutes(player[key]) : safe(player[key], kind === 'pct' ? '%' : ''),
      fill: fill(player[key], league.map(p => p[key]), lower),
    })),
  }
}

function totals(player: Row): string[] {
  const n = (key: string) => String(player[key] || 0)
  const made = (key: string) => `${n(`total_${key}m`)}${JOINER}${n(`total_${key}a`)}`
  return [n('games_played'), minutes(player.total_minutes || 0), n('total_pts'), made('p1'), made('p2'), made('p3'), n('total_ro'), n('total_rd'), n('total_rt'),
    n('total_assist'), n('total_st'), n('total_to'), n('total_bs'), n('total_pf'), n('total_val')]
}

/** The three tables of the page of `player` against `players` (everyone of the competition). */
export function playerTables(player: PlayerStat, players: PlayerStat[]): PlayerTables {
  const row = player as unknown as Row
  const league = players as unknown as Row[]
  return { averages: coloured(row, league, AVERAGES), totals: { headers: TOTALS_HEADERS, cells: totals(row) }, advanced: coloured(row, league, ADVANCED) }
}

/** The age on `today` of a `dd/mm/yyyy` (or `dd-mm-yyyy`) birth date, or `null` when it is not a date. */
export function ageOn(birth: string | null | undefined, today: Date): number | null {
  const match = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/.exec((birth ?? '').trim())
  if (!match) return null
  const [day, month, year] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const real = new Date(year, month - 1, day)
  if (real.getFullYear() !== year || real.getMonth() !== month - 1 || real.getDate() !== day) return null
  const before = (today.getMonth() + 1) * 100 + today.getDate() < month * 100 + day
  return today.getFullYear() - year - (before ? 1 : 0)
}

// ── The document ──────────────────────────────────────────────────────────────

const CM = 567                                                      // twips per centimetre
const BLANK = '___________'
const FILL_NOTES = '_'.repeat(80)

function bytesOf(dataUrl: string | null | undefined): { data: Uint8Array; type: 'png' | 'jpg' } | null {
  const match = /^data:image\/(png|jpeg);base64,(.+)$/.exec(dataUrl ?? '')
  if (!match) return null
  const binary = atob(match[2])
  return { data: Uint8Array.from(binary, c => c.charCodeAt(0)), type: match[1] === 'png' ? 'png' : 'jpg' }
}

/** The pixel size of a PNG or a JPEG (to keep its proportions), `null` when it cannot be read. */
function sizeOf(image: { data: Uint8Array; type: 'png' | 'jpg' }): { width: number; height: number } | null {
  const d = image.data
  if (image.type === 'png') return d.length > 24 ? { width: new DataView(d.buffer, d.byteOffset).getUint32(16), height: new DataView(d.buffer, d.byteOffset).getUint32(20) } : null
  for (let i = 2; i + 9 < d.length;) {
    if (d[i] !== 0xff) { i++; continue }
    const marker = d[i + 1]
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) return { height: (d[i + 5] << 8) | d[i + 6], width: (d[i + 7] << 8) | d[i + 8] }
    i += 2 + ((d[i + 2] << 8) | d[i + 3])
  }
  return null
}

/** The charts of a player, as PNG bytes: the heatmap and the zones of his shots (none when he has no shots) and his radar. */
export interface PlayerCharts { heatmap?: Uint8Array; zones?: Uint8Array; radar?: Uint8Array }

export interface ScoutingDocxInput {
  /** Everyone of the competition (the colours are measured against all of them); the page of each player of `teamName` is made. */
  players: PlayerStat[]
  teamName: string
  /** The crest, the photos and the identity of the team (`images/` of the publication); `null` for a competition that has none (an older season, FBCYL). */
  images: TeamImages | null
  /** The charts of each player by `player_id`; a page has the sections of the charts it has. */
  charts?: Record<string, PlayerCharts>
  today: Date
  /** `dd/mm/yyyy`, as the header prints it. */
  date: string
}

/** The DOCX of the individual scouting of a team. Throws when the team has no players. */
export async function scoutingDocx(input: ScoutingDocxInput): Promise<Blob> {
  const roster = input.players.filter(p => p.team_name === input.teamName)
  if (!roster.length) throw new Error('El equipo no tiene jugadores en esta competición.')
  const lib = await import('docx')
  const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType, ImageRun, HeadingLevel, PageBreak, BorderStyle, VerticalAlign, TableLayoutType } = lib

  const line = { style: BorderStyle.SINGLE, size: 4, color: 'A0A0A0' }
  const borders = { top: line, bottom: line, left: line, right: line }
  const none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' }
  const noBorders = { top: none, bottom: none, left: none, right: none }
  const logo = bytesOf(input.images?.logo)

  const picture = (image: NonNullable<ReturnType<typeof bytesOf>>, o: { height?: number; width?: number }) => {      // inches
    const size = sizeOf(image) ?? { width: 1, height: 1 }
    const [width, height] = o.width ? [Math.round(o.width * 96), Math.round((o.width * 96 * size.height) / size.width)] : [Math.round(((o.height ?? 1) * 96 * size.width) / size.height), Math.round((o.height ?? 1) * 96)]
    return new ImageRun({ type: image.type, data: image.data, transformation: { width: Math.max(1, width), height: Math.max(1, height) }, altText: { title: 'imagen', description: 'imagen', name: 'imagen' } })
  }
  const paragraph = (text: string, size: number, o: { bold?: boolean; align?: (typeof AlignmentType)[keyof typeof AlignmentType]; color?: string } = {}) =>
    new Paragraph({ alignment: o.align, children: [new TextRun({ text, bold: o.bold, size, color: o.color })] })
  const heading = (text: string) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text })] })

  const header = () => new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [new TableRow({ children: [
      new TableCell({ borders, verticalAlign: VerticalAlign.CENTER, children: [logo ? new Paragraph({ alignment: AlignmentType.CENTER, children: [picture(logo, { height: 0.6 })] }) : paragraph(input.teamName, 22)] }),
      new TableCell({ borders, children: [
        paragraph(`Scouting Individual — ${input.teamName}`, 24, { bold: true, align: AlignmentType.RIGHT, color: '1A1A4E' }),
        paragraph(input.date, 18, { align: AlignmentType.RIGHT }),
      ] }),
    ] })],
  })

  const identity = (player: PlayerStat) => {
    const extra = input.images?.players[String(player.player_id)]
    const age = ageOn(extra?.birth_date, input.today)
    const photo = bytesOf(extra?.photo)
    const fact = (label: string, value: string) => new Paragraph({ children: [new TextRun({ text: `${label}: `, bold: true }), new TextRun({ text: value })] })
    return new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [new TableRow({ children: [
        new TableCell({ borders: noBorders, children: [
          new Paragraph({ children: [new TextRun({ text: `#${extra?.no ?? ''}  ${player.player_name ?? '—'}`, bold: true, size: 28 })] }),
          fact('Nac.', extra?.birth_date || BLANK), fact('Edad', age === null ? BLANK : `${age} años`), fact('Altura', extra?.height || BLANK), fact('Posición', BLANK),
        ] }),
        new TableCell({ borders: noBorders, verticalAlign: VerticalAlign.CENTER, children: [photo ? new Paragraph({ alignment: AlignmentType.CENTER, children: [picture(photo, { height: 1.3 })] }) : paragraph('[FOTO]', 20)] }),
      ] })],
    })
  }

  const statsTable = (headers: string[], cells: Cell[], o: { widths?: number[] } = {}) => new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    ...(o.widths ? { layout: TableLayoutType.FIXED, columnWidths: o.widths } : {}),
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => new TableCell({ borders, width: o.widths ? { size: o.widths[i], type: WidthType.DXA } : undefined, children: [paragraph(h, o.widths ? 13 : 14, { bold: true, align: AlignmentType.CENTER })] })) }),
      new TableRow({ children: cells.map((c, i) => new TableCell({
        borders, width: o.widths ? { size: o.widths[i], type: WidthType.DXA } : undefined,
        shading: c.fill ? { type: ShadingType.CLEAR, color: 'auto', fill: c.fill } : undefined,
        children: [paragraph(c.text, o.widths ? 14 : 16, { align: AlignmentType.CENTER })],
      })) }),
    ],
  })

  const png = (bytes: Uint8Array) => ({ data: bytes, type: 'png' as const })
  const charts = (player: PlayerStat): Array<InstanceType<typeof Paragraph> | InstanceType<typeof Table>> => {
    const mine = input.charts?.[String(player.player_id)]
    if (!mine) return []
    const out: Array<InstanceType<typeof Paragraph> | InstanceType<typeof Table>> = []
    if (mine.heatmap || mine.zones) {
      const cell = (bytes?: Uint8Array) => new TableCell({ borders: noBorders, verticalAlign: VerticalAlign.CENTER, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: bytes ? [picture(png(bytes), { height: 2.5 })] : [] })] })
      out.push(heading('3. Perfil de Lanzamiento'), new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows: [new TableRow({ children: [cell(mine.heatmap), cell(mine.zones)] })] }))
    }
    if (mine.radar) {
      out.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [new TextRun({ text: '4. Perfil de Juego' })] }),
        new Paragraph({ alignment: AlignmentType.CENTER, children: [picture(png(mine.radar), { width: 5.5 })] }))
    }
    return out
  }

  const page = (player: PlayerStat): Array<InstanceType<typeof Paragraph> | InstanceType<typeof Table>> => {
    const t = playerTables(player, input.players)
    const widths = [0.7, 1.5, 0.8, 2.0, 2.0, 2.0, 0.7, 0.7, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8].map(cm => Math.round(cm * CM))        // PJ MIN PTS TL T2 T3 RO RD RT AST ROB BP TAP FP VAL
    return [
      header(), identity(player),
      heading('1. Estadística General'),
      paragraph('Promedios por partido:', 20, { bold: true }), statsTable(t.averages.headers, t.averages.cells),
      paragraph('Totales acumulados:', 20, { bold: true }), statsTable(t.totals.headers, t.totals.cells.map(text => ({ text, fill: null })), { widths }),
      heading('2. Estadística Avanzada'), statsTable(t.advanced.headers, t.advanced.cells),
      ...charts(player),
      heading('5. Notas del cuerpo técnico'), ...Array.from({ length: 6 }, () => new Paragraph({ children: [new TextRun({ text: FILL_NOTES })] })),
    ]
  }

  const children = roster.flatMap((player, i) => (i < roster.length - 1 ? [...page(player), new Paragraph({ children: [new PageBreak()] })] : page(player)))
  const doc = new Document({
    creator: 'BasketLab', title: `Scouting Individual — ${input.teamName}`,
    sections: [{ properties: { page: { margin: { top: Math.round(1.5 * CM), bottom: Math.round(1.5 * CM), left: Math.round(1.8 * CM), right: Math.round(1.8 * CM) } } }, children }],
  })
  return Packer.toBlob(doc)
}
