// The radar of a player of the individual scouting (issue #717, 17c): the sixteen metrics in four groups, each normalised 0-100 between the minimum and the maximum of the league (the reverse
// ones, where less is better, inverted), against the league average as a dashed line. The values are a port of `RadarChart` (`calculate_metrics_from_stats`, `normalize_values`; parity:
// `radarChart.test.ts` against `tests/local_vectors/scouting_docx.json`); the drawing is an SVG in the paper palette that the browser turns into a PNG for the DOCX.
import type { PlayerStat } from '@/api/client'
import { PAPER } from '@design/paper'
import { npMean } from '@/localdata/pyMath'

type Row = Record<string, unknown>

const GROUPS = [
  { name: 'Defensa', colour: PAPER.bad, metrics: ['TAP%', 'RD%', 'DRating', 'STL%'], reverse: ['DRating'] },
  { name: 'Tiro', colour: PAPER.own, metrics: ['TS%', 'T3%', 'T2%', 'TL%'], reverse: [] as string[] },
  { name: 'Manejo', colour: PAPER.ok, metrics: ['AST%', 'TO%', 'AST Ratio', 'AST/TO'], reverse: ['TO%'] },
  { name: 'Estilo', colour: PAPER.conceded, metrics: ['AST/USG', '3Pr', 'FTr', 'USG%'], reverse: [] as string[] },
]
const FIELD: Record<string, string> = {
  'TAP%': 'blk_pct', 'RD%': 'drb_pct', DRating: 'drating', 'STL%': 'stl_pct', 'TS%': 'ts', 'T3%': 'fg3_pct', 'T2%': 'fg2_pct', 'TL%': 'ft_pct',
  'AST%': 'ast_pct', 'TO%': 'tov_pct', 'AST Ratio': 'ast_ratio', 'AST/TO': 'ast_to_ratio', 'AST/USG': 'ast_usg', '3Pr': 'three_pr', FTr: 'ftr', 'USG%': 'usage',
}
export const RADAR_LABELS = GROUPS.flatMap(g => g.metrics)

export interface RadarModel { values: number[]; averages: number[] }

/** `dict.get(key, default)`: the default only when the key is absent (a `null` is a value). */
const get = (row: Row, key: string, fallback: unknown): unknown => (key in row ? row[key] : fallback)

/** `prep_player_for_radar`: the aliases the radar reads, without overwriting what the player has. */
function prepared(player: Row): Row {
  const row: Row = { ...player }
  for (const [alias, source] of [['ts', 'true_shooting'], ['usage', 'usage_pct'], ['tov_pct', 'tov_pct_adv']] as const) if (!(alias in row)) row[alias] = get(row, source, 0)
  return row
}

/** `calculate_metrics_from_stats`: a rate that is `null` means «no data» and stays `null` (the chart draws it on the league average, never as a zero). */
function metrics(player: Row): Row {
  const count = (key: string): number => (player[key] === null || player[key] === undefined ? 0 : Number(player[key]))
  const pct = (made: string, attempted: string): number | null => (get(player, attempted, 1) === null ? null : (count(made) / Math.max(count(attempted), 1)) * 100)
  const out: Row = {
    ts: get(player, 'ts', 0), fg3_pct: pct('total_p3m', 'total_p3a'), fg2_pct: pct('total_p2m', 'total_p2a'), ft_pct: pct('total_p1m', 'total_p1a'),
    ast_pct: get(player, 'ast_pct', 0), tov_pct: get(player, 'tov_pct', 0), stl_pct: get(player, 'stl_pct', 0), blk_pct: get(player, 'blk_pct', 0), drb_pct: get(player, 'drb_pct', 0),
    drating: get(player, 'drating', 100),
  }
  if (['ast_ratio', 'ast_to_ratio', 'ast_usg'].every(k => player[k] !== null && player[k] !== undefined)) {
    Object.assign(out, { ast_ratio: player.ast_ratio, ast_to_ratio: player.ast_to_ratio, ast_usg: player.ast_usg })
  } else {
    const assists = count('total_assist'), turnovers = count('total_to'), usage = count('usage')
    const possessions = count('total_p2a') + count('total_p3a') + 0.44 * count('total_p1a') + assists + turnovers
    out.ast_ratio = possessions > 0 ? (100 * assists) / possessions : 0
    out.ast_to_ratio = turnovers > 0 ? assists / turnovers : 0
    out.ast_usg = usage > 0 ? (count('ast_pct') / usage) * 100 : 0
  }
  Object.assign(out, { three_pr: get(player, 'three_pr', 0), ftr: get(player, 'ftr', 0), usage: get(player, 'usage', 0) })
  return out
}

/** `normalize_values`: 0-100 between the league's minimum and maximum, inverted for the reverse metrics, 50 when the league does not vary; no data → the league average. */
export function radarModel(player: PlayerStat, league: PlayerStat[]): RadarModel {
  const mine = metrics(prepared(player as unknown as Row))
  const all = (league as unknown as Row[]).map(p => metrics(prepared(p)))
  const values: number[] = [], averages: number[] = []
  for (const group of GROUPS) {
    for (const metric of group.metrics) {
      const field = FIELD[metric]
      const mineValue = mine[field] as number | null
      const known = all.map(p => p[field]).filter((v): v is number => v !== null && v !== undefined)
      if (!known.length) { values.push(0); averages.push(0); continue }
      const mean = npMean(known), low = Math.min(...known), high = Math.max(...known), span = high - low
      const reverse = group.reverse.includes(metric)
      const scale = (v: number) => (reverse ? (100 * (high - v)) / span : (100 * (v - low)) / span)
      if (mineValue === null) {
        const middle = span <= 0 ? 50 : scale(mean)
        values.push(middle); averages.push(middle)
      } else if (span > 0) {
        values.push(scale(mineValue)); averages.push(scale(mean))
      } else {
        values.push(50); averages.push(50)
      }
    }
  }
  return { values, averages }
}

const escape = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const f = (n: number) => n.toFixed(2)
const clamp = (v: number) => Math.max(0, Math.min(100, v))

export const RADAR_SIZE = { width: 640, height: 540 }

/** The radar as an SVG (bars from the centre, group wedges behind, the league average dashed), in the paper palette. */
export function radarSvg(model: RadarModel, playerName: string): string {
  const { width, height } = RADAR_SIZE
  const cx = width / 2, cy = height / 2 + 14, R = 175
  const n = RADAR_LABELS.length, step = (2 * Math.PI) / n
  const at = (theta: number, r: number): [number, number] => [cx + r * Math.cos(theta), cy - r * Math.sin(theta)]
  const sector = (a: number, b: number, r: number) => {
    const [x1, y1] = at(a, r), [x2, y2] = at(b, r)
    return `M ${f(cx)} ${f(cy)} L ${f(x1)} ${f(y1)} A ${f(r)} ${f(r)} 0 ${b - a > Math.PI ? 1 : 0} 0 ${f(x2)} ${f(y2)} Z`
  }
  const parts: string[] = [`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" font-family="Helvetica, Arial, sans-serif">`,
    `<rect width="${width}" height="${height}" fill="${PAPER.surface}"/>`,
    `<text x="${width / 2}" y="26" text-anchor="middle" font-size="18" font-weight="bold" fill="${PAPER.ink}">${escape(`Análisis Radar - ${playerName}`)}</text>`]
  let index = 0
  for (const group of GROUPS) {
    const first = index, last = index + group.metrics.length - 1
    parts.push(`<path d="${sector(first * step - step / 2, last * step + step / 2, R)}" fill="${group.colour}" fill-opacity="0.1"/>`)
    index += group.metrics.length
  }
  for (const k of [25, 50, 75, 100]) parts.push(`<circle cx="${f(cx)}" cy="${f(cy)}" r="${f((R * k) / 100)}" fill="none" stroke="${PAPER.line}" stroke-dasharray="4 3"/>`)
  RADAR_LABELS.forEach((label, i) => {
    const theta = i * step
    const group = GROUPS.find(g => g.metrics.includes(label))!
    const [sx, sy] = at(theta, R), [lx, ly] = at(theta, R + 16)
    const bar = sector(theta - (step * 0.8) / 2, theta + (step * 0.8) / 2, (R * clamp(model.values[i])) / 100)
    parts.push(`<line x1="${f(cx)}" y1="${f(cy)}" x2="${f(sx)}" y2="${f(sy)}" stroke="${PAPER.line}" stroke-dasharray="4 3"/>`)
    parts.push(`<path data-bar="${escape(label)}" d="${bar}" fill="${group.colour}" fill-opacity="0.7" stroke="${PAPER.surface}" stroke-width="1"/>`)
    parts.push(`<text x="${f(lx)}" y="${f(ly + 4)}" text-anchor="middle" font-size="11" fill="${PAPER.ink}">${escape(label)}</text>`)
  })
  const line = [...model.averages, model.averages[0]].map((v, i) => at((i % n) * step, (R * clamp(v)) / 100)).map(([x, y]) => `${f(x)},${f(y)}`).join(' ')
  parts.push(`<polyline points="${line}" fill="none" stroke="${PAPER.ink}" stroke-opacity="0.8" stroke-width="3" stroke-dasharray="8 5"/>`)
  index = 0
  for (const group of GROUPS) {
    const middle = (index + (group.metrics.length - 1) / 2) * step
    const [gx, gy] = at(middle, R * 1.34), w = group.name.length * 9 + 22
    parts.push(`<rect x="${f(gx - w / 2)}" y="${f(gy - 13)}" width="${w}" height="26" rx="8" fill="${PAPER.surface}" fill-opacity="0.9" stroke="${group.colour}" stroke-width="2"/>`)
    parts.push(`<text x="${f(gx)}" y="${f(gy + 5)}" text-anchor="middle" font-size="14" font-weight="bold" fill="${group.colour}">${group.name}</text>`)
    index += group.metrics.length
  }
  parts.push(`<line x1="${width - 150}" y1="52" x2="${width - 118}" y2="52" stroke="${PAPER.ink}" stroke-width="3" stroke-dasharray="8 5"/>`,
    `<text x="${width - 112}" y="56" font-size="11" fill="${PAPER.ink}">Promedio Liga</text></svg>`)
  return parts.join('')
}
