// The search of BasketLab Talent (epic #872, B3 #879): what the filters mean, as plain functions over the rows of the publication (no React, no network).
//
// Rules that were decided, not guessed:
//  - the AGE is the one of 31/12 of the year the season starts in (the sporting-year convention), so it is the same all season long and comparable between players;
//  - a field that nobody says (FEB leaves height and position empty for many players, FBCYL has no bio) is NO DATA: it is never read as 0 and never dropped without saying so.
//    A row without the data a filter asks for is hidden unless «include those without data» is on, and the result says how many are hidden for that reason;
//  - competitions of another federation, level or gender can be mixed, with a warning: the percentiles are those of the player in HIS competition;
//  - the search starts on the latest season published.
import type { TalentCompetitionEntry, TalentPercentiles, TalentRow } from './data'

export type PositionGroup = 'G' | 'F' | 'C'
export const POSITION_GROUPS: PositionGroup[] = ['G', 'F', 'C']
export type Metric = keyof TalentPercentiles

/** A row of the search: the row of the publication plus the competition it belongs to and the age on 31/12. */
export type SearchRow = TalentRow & {
  comp_key: string; competition: string; season: string; season_label: string; gender?: 'F' | 'M'; level?: number; age: number | null
}

export interface SearchFilters {
  ageMin: number | null; ageMax: number | null
  heightMin: number | null; heightMax: number | null
  groups: PositionGroup[]
  metric: Metric | ''
  pctMin: number | null
  onlyEligible: boolean
  includeUnknown: boolean
  text: string
}

export const NO_FILTERS: SearchFilters = { ageMin: null, ageMax: null, heightMin: null, heightMax: null, groups: [], metric: '', pctMin: null, onlyEligible: false, includeUnknown: false, text: '' }

/** Most competitions the search opens by itself: each one is a file to download, so a longer list is for the person to choose from. */
export const MAX_AUTO_COMPETITIONS = 12

/** The age on 31/12 of the year the season starts in (everyone has had their birthday by then), or None when the date or the season cannot be read. */
export function ageOn1231(birth: string | null, season: string): number | null {
  const born = /^(\d{4})-(\d{2})-(\d{2})$/.exec(birth ?? '')
  const year = /^\d{4}$/.test(season) ? Number(season) : NaN
  if (!born || Number.isNaN(year)) return null
  const age = year - Number(born[1])
  return age >= 0 && age <= 70 ? age : null
}

const plain = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().split(/\s+/).filter(Boolean).join(' ')

export interface Hidden { age: number; height: number; position: number; metric: number; total: number }

type Verdict = 'pass' | 'fail' | 'unknown'
const range = (value: number | null, min: number | null, max: number | null): Verdict => {
  if (min === null && max === null) return 'pass'
  if (value === null) return 'unknown'
  return (min === null || value >= min) && (max === null || value <= max) ? 'pass' : 'fail'
}

function verdicts(row: SearchRow, f: SearchFilters): Record<'age' | 'height' | 'position' | 'metric', Verdict> {
  const percentile = f.metric ? row.pct?.[f.metric] ?? null : null
  return {
    age: range(row.age, f.ageMin, f.ageMax),
    height: range(row.height, f.heightMin, f.heightMax),
    position: f.groups.length === 0 ? 'pass' : row.position_group === null ? 'unknown' : f.groups.includes(row.position_group) ? 'pass' : 'fail',
    metric: f.metric && f.pctMin !== null ? range(percentile, f.pctMin, null) : 'pass',
  }
}

function matchesText(row: SearchRow, text: string): boolean {
  const wanted = plain(text)
  return !wanted || plain(`${row.name} ${row.full_name ?? ''} ${row.team_name}`).includes(wanted)
}

/** The rows that pass every filter, in the order they came, and how many were hidden only because they do not say a field a filter asks for. */
export function applySearch(rows: SearchRow[], f: SearchFilters): { rows: SearchRow[]; hidden: Hidden } {
  const hidden: Hidden = { age: 0, height: 0, position: 0, metric: 0, total: 0 }
  const kept: SearchRow[] = []
  for (const row of rows) {
    if ((f.onlyEligible && !row.eligible) || !matchesText(row, f.text)) continue
    const v = verdicts(row, f)
    const fields = Object.keys(v) as (keyof typeof v)[]
    if (fields.some(k => v[k] === 'fail')) continue
    const unknown = fields.filter(k => v[k] === 'unknown')
    if (unknown.length === 0 || f.includeUnknown) { kept.push(row); continue }
    unknown.forEach(k => { hidden[k] += 1 })
    hidden.total += 1
  }
  return { rows: kept, hidden }
}

/** A warning when the competitions chosen are not alike (federation, level or gender), else null: they can be mixed, but their percentiles are not comparable. */
export function mixNotice(entries: TalentCompetitionEntry[]): string | null {
  const kinds = new Set(entries.map(e => `${e.league}|${e.level ?? ''}|${e.gender ?? ''}`))
  return kinds.size > 1
    ? 'Mezclas competiciones de distinta federación, nivel o sexo: los percentiles son los del jugador dentro de su competición y no se pueden comparar entre ellas.'
    : null
}

/** The latest season published and its competitions (none when there are more than `MAX_AUTO_COMPETITIONS`: you choose). */
export function defaultSearch(entries: TalentCompetitionEntry[]): { season: string; keys: string[] } {
  const latest = Math.max(...entries.map(e => Number(e.season)).filter(Number.isFinite))
  if (!Number.isFinite(latest)) return { season: '', keys: [] }
  const keys = entries.filter(e => Number(e.season) === latest).map(e => e.key)
  return { season: String(latest), keys: keys.length > MAX_AUTO_COMPETITIONS ? [] : keys }
}

const number = (text: string | null, min: number, max: number): number | null => {
  if (text === null || text.trim() === '') return null
  const n = Number(text)
  return Number.isFinite(n) && n >= min && n <= max ? n : null
}

const PARAM_NUMBERS = [['amin', 'ageMin'], ['amax', 'ageMax'], ['hmin', 'heightMin'], ['hmax', 'heightMax'], ['p', 'pctMin']] as const
const NUMBER_LIMITS: Record<string, [number, number]> = { ageMin: [0, 70], ageMax: [0, 70], heightMin: [100, 260], heightMax: [100, 260], pctMin: [0, 100] }

export function filtersToParams(f: SearchFilters): URLSearchParams {
  const p = new URLSearchParams()
  for (const [key, field] of PARAM_NUMBERS) if (f[field] !== null) p.set(key, String(f[field]))
  if (f.groups.length) p.set('pos', f.groups.join(','))
  if (f.metric) p.set('m', f.metric)
  if (f.onlyEligible) p.set('e', '1')
  if (f.includeUnknown) p.set('u', '1')
  if (f.text) p.set('q', f.text)
  return p
}

/** The filters of an address; what is not understood is left out (a shared link must open, not fail). */
export function filtersFromParams(p: URLSearchParams): SearchFilters {
  const out: SearchFilters = { ...NO_FILTERS }
  for (const [key, field] of PARAM_NUMBERS) out[field] = number(p.get(key), ...NUMBER_LIMITS[field])
  const wanted = (p.get('pos') ?? '').split(',')
  out.groups = POSITION_GROUPS.filter(g => wanted.includes(g))
  const metric = p.get('m') as Metric | null
  out.metric = metric && METRICS.some(m => m.key === metric) ? metric : ''
  out.onlyEligible = p.get('e') === '1'
  out.includeUnknown = p.get('u') === '1'
  out.text = p.get('q') ?? ''
  return out
}

/** The metrics a percentile filter can ask for, with the name the staff reads. */
export const METRICS: { key: Metric; label: string }[] = [
  { key: 'pts', label: 'Puntos / 40' }, { key: 'ast', label: 'Asistencias / 40' }, { key: 'orb', label: 'Reb. ofensivos / 40' }, { key: 'drb', label: 'Reb. defensivos / 40' },
  { key: 'stl', label: 'Robos / 40' }, { key: 'blk', label: 'Tapones / 40' }, { key: 'tov', label: 'Pérdidas / 40' }, { key: 'fg3a', label: 'Triples intentados / 40' },
  { key: 'fg2a', label: 'Dobles intentados / 40' }, { key: 'usage', label: 'Uso' }, { key: 'efg', label: 'eFG%' }, { key: 'ftr', label: 'Tiros libres / tiro' }, { key: 'ts', label: 'TS%' },
  { key: 'usage_pct', label: 'Uso (%)' }, { key: 'pie', label: 'PIE' },
]

const COLUMNS: { key: string; label: string; value: (r: SearchRow) => unknown }[] = [
  { key: 'name', label: 'Jugador', value: r => r.full_name ?? r.name },
  { key: 'team_name', label: 'Equipo', value: r => r.team_name },
  { key: 'competition', label: 'Competición', value: r => r.competition },
  { key: 'season_label', label: 'Temporada', value: r => r.season_label },
  { key: 'age', label: 'Edad (31/12)', value: r => r.age },
  { key: 'height', label: 'Altura (cm)', value: r => r.height },
  { key: 'position', label: 'Posición', value: r => r.position ?? r.position_group },
  { key: 'games', label: 'PJ', value: r => r.games },
  { key: 'minutes', label: 'Min', value: r => Math.round(r.minutes / 60) },
  { key: 'pts40', label: 'Pts/40', value: r => r.per40?.pts ?? null },
  { key: 'ast40', label: 'Ast/40', value: r => r.per40?.ast ?? null },
  { key: 'reb40', label: 'Reb/40', value: r => (r.per40 ? Math.round((r.per40.orb + r.per40.drb) * 100) / 100 : null) },
]

/** The CSV of the result: a header and a row per player; what nobody says is an empty cell (null), never a 0. */
export function csvOf(rows: SearchRow[]): { headers: { key: string; label: string }[]; data: Record<string, unknown>[] } {
  return {
    headers: COLUMNS.map(({ key, label }) => ({ key, label })),
    data: rows.map(r => Object.fromEntries(COLUMNS.map(c => [c.key, c.value(r) ?? null]))),
  }
}
