/** The box score as a table (issue #593): which rows a team has, which columns and what each cell says. Pure functions of the snapshot and of ``analysis.boxscore``. */
import type { AdvancedKey, BoxscoreEntry, LastStat, PlayerStats, Snapshot } from '../../engine/types'

export type Mode = 'normal' | 'advanced'

export interface Row {
  id: string
  kind: 'player' | 'team' | 'total'
  name: string
  onCourt: boolean
  /** Seconds played. */
  minutes: number
  pts: number
  /** Plus/minus (null in the rows of the team). */
  pm: number | null
  pf: number
  fd: number
  stats: PlayerStats
  entry?: BoxscoreEntry
}

export interface Column {
  id: string
  label: string
  /** What it is, in words (the tooltip and the accessible name). */
  title: string
  /** The key of the deviation (``entry.dev``) that colours the cell, if the package has an average to compare it with. */
  dev?: string
  /** The keys of ``last_stat`` that change the cell. */
  keys?: string[]
  advanced?: AdvancedKey
  text(row: Row): string
}

const EMPTY: PlayerStats = { fg2m: 0, fg2a: 0, fg3m: 0, fg3a: 0, ftm: 0, fta: 0, orb: 0, drb: 0, tov: 0, stl: 0, ast: 0, blk: 0 }
const DASH = '—'

export const mmss = (seconds: number): string => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
const decimal = (value: number | null | undefined, digits = 1): string => (value === null || value === undefined ? DASH : value.toFixed(digits).replace('.', ','))
const signed = (value: number | null): string => (value === null ? '' : value > 0 ? `+${value}` : String(value))
const ratio = (made: number, attempted: number): string => `${made}/${attempted}`
const fg = (s: PlayerStats) => ({ made: s.fg2m + s.fg3m, attempted: s.fg2a + s.fg3a })

/** Only the players of the team (the rows of the team and of the totals are made apart). The ones on court go first; within each group the order is the alphabetical one,
 *  so a row never jumps because of the minutes. */
export function playerRows(snapshot: Snapshot, teamId: string, entries: Record<string, BoxscoreEntry> | undefined): Row[] {
  const rows = Object.entries(snapshot.players ?? {})
    .filter(([, p]) => p.team_id === teamId)
    .map(([id, p]): Row => ({ id, kind: 'player', name: p.name, onCourt: p.on_court, minutes: p.minutes, pts: p.pts, pm: p.pm, pf: p.pf, fd: p.fd ?? 0, stats: p.stats, entry: entries?.[id] }))
  return rows.sort((a, b) => Number(b.onCourt) - Number(a.onCourt) || a.name.localeCompare(b.name, 'es'))
}

/** The row of the team (what nobody owns: rebounds and turnovers of the team) and the totals, as the PDF has them. */
export function teamRows(snapshot: Snapshot, teamId: string, players: Row[]): { team: Row; totals: Row } {
  const team = snapshot.teams[teamId]?.stats
  const sum = (key: keyof PlayerStats) => players.reduce((acc, r) => acc + r.stats[key], 0)
  const stats: PlayerStats = team ? { ...EMPTY, ...team } : { ...EMPTY }
  const nobody: PlayerStats = {
    ...EMPTY, orb: Math.max(0, stats.orb - sum('orb')), drb: Math.max(0, stats.drb - sum('drb')),
    tov: Math.max(0, stats.tov - sum('tov')) + (team?.tov_team ?? 0),
  }
  const totals: PlayerStats = { ...stats, tov: stats.tov + (team?.tov_team ?? 0) }
  return {
    team: { id: `${teamId}:team`, kind: 'team', name: 'Equipo', onCourt: false, minutes: 0, pts: 0, pm: null, pf: 0, fd: 0, stats: nobody },
    totals: { id: `${teamId}:total`, kind: 'total', name: 'Totales', onCourt: false, minutes: players.reduce((acc, r) => acc + r.minutes, 0), pts: team?.pts ?? snapshot.score[teamId] ?? 0,
      pm: null, pf: players.reduce((acc, r) => acc + r.pf, 0), fd: players.reduce((acc, r) => acc + r.fd, 0), stats: totals,
      entry: { val: players.reduce((acc, r) => acc + (r.entry?.val ?? 0), 0), adv: {} as BoxscoreEntry['adv'], dev: {} } },
  }
}

const SHOOTING = ['fg2m', 'fg2a', 'fg3m', 'fg3a']
const only = (rows: Row['kind'][], text: (r: Row) => string) => (r: Row): string => (rows.includes(r.kind) ? text(r) : '')

export const NORMAL_COLUMNS: Column[] = [
  { id: 'min', label: 'Min', title: 'Minutos jugados', text: only(['player', 'total'], r => mmss(r.minutes)) },
  { id: 'pts', label: 'Pts', title: 'Puntos', dev: 'pts', keys: ['pts'], text: only(['player', 'total'], r => String(r.pts)) },
  { id: 't2', label: 'T2', title: 'Tiros de 2 anotados/intentados', keys: ['fg2m', 'fg2a'], text: only(['player', 'total'], r => ratio(r.stats.fg2m, r.stats.fg2a)) },
  { id: 't3', label: 'T3', title: 'Triples anotados/intentados', dev: 'fg3m', keys: ['fg3m', 'fg3a'], text: only(['player', 'total'], r => ratio(r.stats.fg3m, r.stats.fg3a)) },
  { id: 'tc', label: 'TC', title: 'Tiros de campo anotados/intentados', keys: SHOOTING, text: only(['player', 'total'], r => ratio(fg(r.stats).made, fg(r.stats).attempted)) },
  { id: 'tl', label: 'TL', title: 'Tiros libres anotados/intentados', dev: 'ftm', keys: ['ftm', 'fta'], text: only(['player', 'total'], r => ratio(r.stats.ftm, r.stats.fta)) },
  { id: 'ro', label: 'RO', title: 'Rebotes ofensivos', dev: 'orb', keys: ['orb'], text: r => String(r.stats.orb) },
  { id: 'rd', label: 'RD', title: 'Rebotes defensivos', dev: 'drb', keys: ['drb'], text: r => String(r.stats.drb) },
  { id: 'rt', label: 'RT', title: 'Rebotes totales', dev: 'reb', keys: ['orb', 'drb'], text: r => String(r.stats.orb + r.stats.drb) },
  { id: 'ast', label: 'As', title: 'Asistencias', dev: 'ast', keys: ['ast'], text: only(['player', 'total'], r => String(r.stats.ast)) },
  { id: 'stl', label: 'Rec', title: 'Recuperaciones (robos)', dev: 'stl', keys: ['stl'], text: only(['player', 'total'], r => String(r.stats.stl)) },
  { id: 'blk', label: 'Tap', title: 'Tapones', dev: 'blk', keys: ['blk'], text: only(['player', 'total'], r => String(r.stats.blk)) },
  { id: 'tov', label: 'Per', title: 'Pérdidas (más es peor)', dev: 'tov', keys: ['tov'], text: r => String(r.stats.tov) },
  { id: 'fc', label: 'FC', title: 'Faltas cometidas (más es peor)', dev: 'pf', keys: ['pf'], text: only(['player', 'total'], r => String(r.pf)) },
  { id: 'fr', label: 'FR', title: 'Faltas recibidas', keys: ['fd'], text: only(['player', 'total'], r => String(r.fd)) },
  { id: 'pm', label: '+/-', title: 'Diferencia de puntos de su equipo con el rival mientras está en pista', text: only(['player'], r => signed(r.pm)) },
  { id: 'val', label: 'Val', title: 'Valoración como la del PDF de FEB, sin descontar los tapones recibidos', text: only(['player', 'total'], r => (r.entry ? String(r.entry.val) : '')) },
]

const advanced = (id: AdvancedKey, label: string, title: string, dev?: string): Column =>
  ({ id, label, title, dev, advanced: id, text: r => (r.kind === 'player' ? decimal(r.entry?.adv?.[id]) : '') })

export const ADVANCED_COLUMNS: Column[] = [
  NORMAL_COLUMNS[0], NORMAL_COLUMNS[NORMAL_COLUMNS.length - 2],
  advanced('usage', 'Usg%', 'Tasa de uso: porcentaje de posesiones del equipo utilizadas por el jugador mientras está en pista'),
  advanced('orating', 'ORtg', 'Rating ofensivo: puntos producidos por cada 100 posesiones individuales'),
  advanced('drating', 'DRtg', 'Rating defensivo: puntos permitidos por cada 100 posesiones cuando está en pista (menor es mejor)'),
  advanced('net_rtg', 'NetRtg', 'Net rating individual: rating ofensivo menos defensivo'),
  advanced('efg', 'eFG%', 'Acierto de tiro de campo ajustado por los triples', 'efg'),
  advanced('ts', 'TS%', 'Acierto real de tiro: puntos por tiro de campo y tiro libre intentados'),
  advanced('ftr', 'FTr', 'Tasa de tiro libre: tiros libres intentados por intento de campo'),
  advanced('three_pr', '3Pr', 'Tasa de triple: proporción de intentos de campo que son triples'),
  advanced('ast_pct', '%AST', 'Porcentaje de canastas del equipo con asistencia del jugador mientras está en pista'),
  advanced('tov_pct', '%TO', 'Porcentaje de posesiones del jugador que acaban en pérdida (menor es mejor)'),
  advanced('stl_pct', '%ROB', 'Porcentaje de posesiones del rival que acaban en robo del jugador'),
  advanced('blk_pct', '%TAP', 'Porcentaje de intentos de 2 del rival tapados por el jugador'),
  advanced('drb_pct', '%RD', 'Porcentaje de rebotes defensivos disponibles capturados por el jugador'),
  advanced('orb_pct', '%RO', 'Porcentaje de rebotes ofensivos disponibles capturados por el jugador'),
  advanced('pie', 'PIE%', 'Impacto relativo del jugador en el partido (Player Impact Estimate)'),
]

export const cellText = (column: Column, row: Row): string => column.text(row)

/** How far a cell is from the average of its player, in [-1, 1] with the sign of good (null: nothing to compare with). */
export function deviationOf(column: Column, row: Row): number | null {
  const value = column.dev && row.kind === 'player' ? row.entry?.dev?.[column.dev] : null
  return typeof value === 'number' ? value : null
}

export interface Highlight {
  row: boolean
  /** Does the column of this cell change with the last action? */
  cell(column: Column): boolean
}

/** What the last action lights for a player: his row and the cells of the columns that changed; null when it is not about him. */
export function highlightFor(last: LastStat | null | undefined, playerId: string): Highlight | null {
  if (!last) return null
  const keys = last.player_id === playerId ? last.keys : last.also.find(a => a.player_id === playerId)?.keys
  if (!keys) return null
  return { row: true, cell: column => (column.keys ?? []).some(k => keys.includes(k)) }
}
