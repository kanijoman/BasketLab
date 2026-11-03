// The weekly report in the browser (issue #716, D4b): the ZIP of PNG the server's `WeeklyReportService` made, from the tables and the charts the page already reads. Same folders, same file names
// and same rows (`weeklyRows`, ported with parity vectors); the tables are drawn as SVG in the paper palette (`weeklyTables`) and the shot charts are the web's own court (`scoutingCharts`), both
// made PNG by the caller's `render` (`svgToPng`). What is missing is left out as the server did (a team with no players, a comparison with no data); only a missing key is an error.
//
//     General/01_Basicas_Toda_Competicion.png … 06_Consistencia_Liga.png (+ _Rival), 05_Ultimo_Partido_{team}.png
//     {team}/1_Estadisticas_Individuales/01_{team}_Promedios.png, 02_…_Totales.png, 03_…_Proyeccion_30min.png
//     {team}/2_Graficos_Lanzamiento/Equipo/{team}_Mapa_Calor.png, _Zonas.png and Jugadoras/{player}/{player}_Mapa_Calor.png, _Zonas.png
import { ScopedAccessError } from '@live-package/crypto'
import type { ShotRawData, ShotZoneData, TeamFilters } from '@/api/client'
import { tableSvg } from '@/lib/weeklyTables'
import {
  ADV_HEADERS, BASIC_HEADERS, CONSISTENCY_HEADERS, LAST_MATCH_HEADERS, advancedRows, basicRows, comparativeAdvancedRows, comparativeBasicRows, consistencyRows, lastMatchRows, playerRows,
  type Comparative, type CVTable, type PlayerMode, type Row,
} from '@/lib/weeklyRows'

/** The last game of a team: its figures and its rival's in that game (rows of the tables), the rival's name and the day. */
export interface LastGame { team: Row; opponent: Row; opponentName: string; date: string }

/** What the report reads: the tables of the competition with the filters, the players, the last game of a team and the shots (of a team, or of one of its players). */
export interface WeeklyData {
  teamStats(filter: TeamFilters): Promise<{ team_stats: Row[]; opponent_stats: Row[] }>
  consistency(): Promise<CVTable>
  lastMatch(teamName: string): Promise<LastGame | null>
  players(): Promise<Row[]>
  shots(teamId: string, player?: string): Promise<ShotRawData[]>
  zones(teamId: string, player?: string): Promise<ShotZoneData[]>
}

export interface WeeklyTeam { id: string; name: string }
export interface WeeklyInput { teamA: WeeklyTeam; teamB: WeeklyTeam; today: Date }
export type Render = (svg: string) => Promise<Uint8Array>
export type Progress = (step: number, total: number, message: string) => void

/** The drawing of the shot charts: the web's court with the lines of its title over it (loaded when there are shots to draw, so the tables do not pay for React's renderer). */
interface Charts { court(mode: 'heatmap' | 'zones', zones: ShotZoneData[], shots: ShotRawData[], title: string[]): string }

async function loadCharts(): Promise<Charts> {
  const { courtSvg, titledSvg } = await import('@/lib/scoutingCharts')
  return { court: (mode, zones, shots, title) => titledSvg(courtSvg(mode, zones, shots), title) }
}

const STEPS = 5
const MIN_PLAYER_SHOTS = 5
const DAY = 86_400_000

/** `_sanitize`: a name as a file name, without what the file systems refuse. */
export const sanitize = (name: string): string => name.replace(/[<>:"/\\|?*]/g, '_').trim()

const isoDay = (ms: number) => new Date(ms).toISOString().slice(0, 10)
const nameOf = (team: Row): string => String(team.team_name ?? team._id ?? '')

/** The files being made: `put` draws an SVG as the PNG at a path, and a drawing the browser cannot make leaves that file out. */
type Put = (path: string, svg: string) => Promise<void>

/** A read that cannot be had is left out of the report (as the server's per-section `try`); a missing key is the reader's to solve, not a hole in the report. */
async function tolerant<T>(read: () => Promise<T>, otherwise: T): Promise<T> {
  try {
    return await read()
  } catch (error) {
    if (error instanceof ScopedAccessError) throw error
    return otherwise
  }
}

function pairs(first: Row[], second: Row[]): Comparative[] {
  if (!first.length || !second.length) return []
  const rest = new Map(second.map(t => [nameOf(t), t]))
  return first.flatMap(t => (rest.has(nameOf(t)) ? [{ monthly: t, rest: rest.get(nameOf(t))! }] : []))
}

async function wholeCompetition(put: Put, tables: { team_stats: Row[]; opponent_stats: Row[] }): Promise<void> {
  for (const [rival, stats] of [[false, tables.team_stats], [true, tables.opponent_stats]] as const) {
    if (!stats.length) continue
    const suffix = rival ? '_Rival' : '', label = rival ? ' (Rival)' : ''
    await put(`General/01_Basicas_Toda_Competicion${suffix}.png`, tableSvg(BASIC_HEADERS, basicRows(stats, rival), `Estadísticas Básicas - Toda la Competición${label}`))
    await put(`General/01_Avanzadas_Toda_Competicion${suffix}.png`, tableSvg(ADV_HEADERS, advancedRows(stats, rival), `Estadísticas Avanzadas - Toda la Competición${label}`))
  }
}

/** A comparison of two halves of the season (won/lost, home/away, the last month / the rest): both tables of the team and of its rivals, with a placeholder when no team has both halves. */
async function comparison(put: Put, prefix: string, label: string, first: { team_stats: Row[]; opponent_stats: Row[] }, second: { team_stats: Row[]; opponent_stats: Row[] }): Promise<void> {
  for (const rival of [false, true]) {
    const comp = pairs(rival ? first.opponent_stats : first.team_stats, rival ? second.opponent_stats : second.team_stats)
    const suffix = rival ? '_Rival' : '', extra = (rival ? ' (Rival)' : '') + (comp.length ? '' : ' (datos insuficientes)')
    const slug = label.replace(/ /g, '_')
    await put(`General/${prefix}_Basicas_${slug}${suffix}.png`, tableSvg(BASIC_HEADERS, comparativeBasicRows(comp, rival), `Estadísticas Básicas - ${label}${extra}`))
    await put(`General/${prefix}_Avanzadas_${slug}${suffix}.png`, tableSvg(ADV_HEADERS, comparativeAdvancedRows(comp, rival), `Estadísticas Avanzadas - ${label}${extra}`))
  }
}

async function general(data: WeeklyData, put: Put, today: Date): Promise<Row[]> {
  const season = await data.teamStats({})
  const consistency = await tolerant(() => data.consistency(), {} as CVTable)
  await wholeCompetition(put, season)
  const cutoff = today.getTime() - 30 * DAY
  const [won, lost, home, away, month, rest] = await Promise.all([
    data.teamStats({ result: 'won' }), data.teamStats({ result: 'lost' }), data.teamStats({ venue: 'home' }), data.teamStats({ venue: 'away' }),
    data.teamStats({ from: isoDay(cutoff) }), data.teamStats({ to: isoDay(cutoff - DAY) }),
  ])
  await comparison(put, '02', 'Ganados vs Perdidos', won, lost)
  await comparison(put, '03', 'Local vs Visitante', home, away)
  await comparison(put, '04', 'Último Mes', month, rest)
  const rows = consistencyRows(consistency)
  if (rows.texts.length) await put('General/06_Consistencia_Liga.png', tableSvg(CONSISTENCY_HEADERS, rows, 'Consistencia Intraequipo - CV% (menor = más consistente)'))
  return season.team_stats
}

/** `_gen_last_match`: the table of the team's last game, if it and its rival have a row of the season to compare with. */
async function lastMatch(data: WeeklyData, put: Put, season: Row[], team: string): Promise<void> {
  const last = await tolerant(() => data.lastMatch(team), null)
  if (!last) return
  const mine = season.find(t => t.team_name === team), theirs = season.find(t => t.team_name === last.opponentName)
  if (!mine || !theirs) return
  const rows = lastMatchRows(last.team, last.opponent, mine, theirs, team, last.opponentName)
  await put(`General/05_Ultimo_Partido_${sanitize(team)}.png`, tableSvg(LAST_MATCH_HEADERS, rows, `Último Partido - ${team} - ${last.date}`))
}

const MODES: Array<[PlayerMode, string, string]> = [['avg', '01', 'Promedios'], ['total', '02', 'Totales'], ['projection', '03', 'Proyeccion_30min']]

async function playerTables(put: Put, players: Row[], team: string): Promise<void> {
  const safe = sanitize(team)
  for (const [mode, number, label] of MODES) {
    const { headers, ...rows } = playerRows(players, mode)
    await put(`${safe}/1_Estadisticas_Individuales/${number}_${safe}_${label}.png`, tableSvg(headers, rows, `${team} - ${label.replace(/_/g, ' ')}`))
  }
}

const score = (shots: ShotRawData[]) => {
  const made = shots.filter(s => s.made).length
  return `${made}/${shots.length} (${(shots.length ? (made / shots.length) * 100 : 0).toFixed(1)}%)`
}

/** The heatmap and the zones of some shots in a folder, under the name of whose they are. */
async function shotCharts(data: WeeklyData, charts: Charts, put: Put, folder: string, file: string, who: string, teamId: string, shots: ShotRawData[], player?: string): Promise<void> {
  const zones = await tolerant(() => data.zones(teamId, player), [])
  await put(`${folder}/${file}_Mapa_Calor.png`, charts.court('heatmap', [], shots, [who, score(shots)]))
  await put(`${folder}/${file}_Zonas.png`, charts.court('zones', zones, shots, [`${who} - Análisis por Zonas`, score(shots)]))
}

async function teamShots(data: WeeklyData, put: Put, team: WeeklyTeam, players: Row[]): Promise<void> {
  const shots = await tolerant(() => data.shots(team.id), [])
  if (!shots.length) return
  const charts = await loadCharts()
  const safe = sanitize(team.name), base = `${safe}/2_Graficos_Lanzamiento`
  await shotCharts(data, charts, put, `${base}/Equipo`, safe, team.name, team.id, shots)
  for (const player of players) {                                     // one at a time: each is a pair of PNG of a few hundred KB
    const id = String(player.player_id), mine = await tolerant(() => data.shots(team.id, id), [])
    if (mine.length < MIN_PLAYER_SHOTS) continue
    const name = String(player.player_name ?? `Jugador ${id}`), file = sanitize(name)
    await shotCharts(data, charts, put, `${base}/Jugadoras/${file}`, file, name, team.id, mine, id)
  }
}

async function teamReport(data: WeeklyData, put: Put, team: WeeklyTeam): Promise<void> {
  const players = (await tolerant(() => data.players(), [])).filter(p => p.team_name === team.name)
  if (players.length) await playerTables(put, players, team.name)
  await teamShots(data, put, team, players)
}

/** The files of the report by path, drawn with `render`. `onProgress` is told the five steps the server's job told. */
export async function weeklyReportFiles(input: WeeklyInput, data: WeeklyData, render: Render, onProgress?: Progress): Promise<Record<string, Uint8Array>> {
  const files: Record<string, Uint8Array> = {}
  const put: Put = async (path, svg) => {
    try {
      files[path] = await render(svg)
    } catch {
      // a drawing the browser cannot make leaves its file out; the report goes on
    }
  }
  const step = (n: number, message: string) => onProgress?.(n, STEPS, message)
  const { teamA, teamB } = input
  step(1, 'Estadísticas generales de competición')
  const season = await general(data, put, input.today)
  step(2, `Último partido — ${teamA.name}`)
  await lastMatch(data, put, season, teamA.name)
  step(3, `Último partido — ${teamB.name}`)
  await lastMatch(data, put, season, teamB.name)
  step(4, `Informe equipo — ${teamA.name}`)
  await teamReport(data, put, teamA)
  step(5, `Informe equipo — ${teamB.name}`)
  await teamReport(data, put, teamB)
  return files
}

/** The report as the ZIP to download (the PNG are already compressed: stored, not deflated again). */
export async function weeklyReportZip(input: WeeklyInput, data: WeeklyData, render: Render, onProgress?: Progress): Promise<Blob> {
  const [files, { zipSync }] = await Promise.all([weeklyReportFiles(input, data, render, onProgress), import('fflate')])
  const zipped = zipSync(Object.fromEntries(Object.entries(files).map(([path, bytes]) => [path, [bytes, { level: 0 }] as [Uint8Array, { level: 0 }]])))
  return new Blob([zipped as BlobPart], { type: 'application/zip' })
}
