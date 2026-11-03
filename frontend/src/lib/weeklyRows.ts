// The rows of the tables of the weekly report (issue #716, D4a): a port of the pure builders of `src/services/_weekly_report_helpers.py` (`build_basic_rows`, `build_advanced_rows`,
// the comparative and last-match ones, `build_player_rows`, `build_consistency_rows`). What a cell says and how it is rated is the same as the server's, to the last digit (parity:
// `weeklyRows.test.ts` against `tests/local_vectors/weekly_rows.json`); what changes is the colour, which here is a `Tone` the drawing (`weeklyTables.ts`) paints with the paper palette
// instead of the dark hexadecimals the matplotlib tables had.
import { percentile } from '@/localdata/playerQuartiles'
import { pyFixed, pyRound } from '@/localdata/pyMath'

/** How a cell is rated: the quartiles best to worst (`q1` … `q4`), `even` (equal to its rival in a last match) or `plain` (no rating). */
export type Tone = 'plain' | 'q1' | 'q2' | 'q3' | 'q4' | 'even'
export interface TableRows { texts: string[][]; tones: Tone[][] }
export type Row = Record<string, unknown>

const QUARTILE_TONES: Tone[] = ['q4', 'q3', 'q2', 'q1']                   // worst → best (higher is better)

export const BASIC_HEADERS = ['Equipo', 'PJ', 'Local', 'Visitante', 'P.Favor', 'P.Contra', 'Pts/P', 'PtsC/P', '%T2', '%T3', '%TL', 'Reb', 'RD', 'RO', 'Ast', 'Rob', 'Pérd', 'Tap']
export const ADV_HEADERS = ['Equipo', 'PJ', 'Ritmo', 'OER', 'DER', 'Net', 'eFG%', 'TS%', '3Pr', 'FTr', 'AST/FG', 'AST%', 'TOV%', 'ROB%', 'TAP%', 'ORB%', 'RD%']
export const LAST_MATCH_HEADERS = ADV_HEADERS

/** A figure of the table and whether LESS is better in it. */
type Field = readonly [string, boolean]

const BASIC_FIELDS: Field[] = [
  ['points_scored', false], ['points_received', true], ['points_per_game', false], ['points_against_per_game', true], ['fg2_percentage', false], ['fg3_percentage', false],
  ['ft_percentage', false], ['total_rebounds', false], ['rebounds_def', false], ['rebounds_off', false], ['assists', false], ['steals', false], ['turnovers', true], ['blocks', false],
]
const ADV_FIELDS: Field[] = [
  ['possessions_per_game', false], ['offensive_rating', false], ['defensive_rating', true], ['net_rating', false], ['efg_percentage', false], ['true_shooting', false],
  ['three_point_rate', false], ['free_throw_rate', false], ['assist_fg_rate', false], ['assist_rate', false], ['turnover_rate', true], ['steal_rate', false],
  ['block_rate', false], ['offensive_rebound_rate', false], ['defensive_rebound_rate', false],
]
const PLAYER_FIELDS: Field[] = [
  ['minutes_per_game', false], ['points_per_game', false], ['fg1_percentage', false], ['fg2_percentage', false], ['fg3_percentage', false], ['total_ro', false], ['total_rd', false],
  ['rebounds_per_game', false], ['assists_per_game', false], ['steals_per_game', false], ['turnovers_per_game', true], ['blocks_per_game', false], ['total_pf', true],
  ['total_rf', false], ['pllss_per_game', false], ['valoracion_per_game', false],
]
export const PLAYER_HEADERS_AVG = ['Jugador', 'PJ', 'Min', 'Pts', '%TL', '%T2', '%T3', 'RO', 'RD', 'Reb', 'Ast', 'Rob', 'BP', 'Tap', 'FP', 'FR', '+/-', 'Val']
export const PLAYER_HEADERS_TOT = ['Jugador', 'PJ', 'Min', 'Pts', 'TL', 'T2', 'T3', 'RO', 'RD', 'Reb', 'Ast', 'Rob', 'BP', 'Tap', 'FP', 'FR', '+/-', 'Val']

/** Python's `float(x or 0)`: a missing figure (or a zero) is 0. */
const num = (value: unknown): number => Number(value || 0)
/** Python's `int(x or 0)`: truncated toward zero. */
const whole = (value: unknown): number => Math.trunc(num(value))
/** Python's `str(x)` of a figure or a name that can be missing. */
const text = (value: unknown): string => (value === null || value === undefined ? 'None' : String(value))
/** `str(team.get('team_name', team.get('_id', '')))`: the name, else the id, else nothing. */
const teamName = (team: Row): string => ('team_name' in team ? text(team.team_name) : text(team._id ?? ''))

/** `sf`: a figure with `decimals` decimals (Python's rounding of the exact ties), `-` when it is missing. */
export const sf = (value: unknown, decimals = 1): string => (value === null || value === undefined ? '-' : pyFixed(Number(value), decimals))

/** `calc_quartiles`: `np.percentile` 25, 50 and 75 of the figures that exist, `[0, 0, 0]` when there are none. */
export function calcQuartiles(values: Array<number | null | undefined>): [number, number, number] {
  const known = values.filter((v): v is number => v !== null && v !== undefined).sort((a, b) => a - b)
  return known.length ? [percentile(known, 0.25), percentile(known, 0.5), percentile(known, 0.75)] : [0, 0, 0]
}

/** `q_color`: the tone of a figure among the quartiles `[q1, q2, q3]` of its column (`reverse`: less is better). */
export function quartileTone(value: number, quartiles: number[], reverse = false): Tone {
  const palette = reverse ? [...QUARTILE_TONES].reverse() : QUARTILE_TONES
  if (value >= quartiles[2]) return palette[3]
  if (value >= quartiles[1]) return palette[2]
  if (value >= quartiles[0]) return palette[1]
  return palette[0]
}

/** `with_diff`: `78.4 (+2.1)`, the figure and its real difference with `other` (points for a percentage); only the figure if there is nothing to compare with. */
export function withDiff(value: number, other: unknown, decimals = 1): string {
  if (other === null || other === undefined) return sf(value, decimals)
  const diff = pyRound(Number(value) - Number(other), decimals)
  return `${sf(value, decimals)} (${diff === 0 ? pyFixed(0, decimals) : pyFixed(diff, decimals, true)})`
}

const columnQuartiles = (rows: Row[], fields: Field[]) => Object.fromEntries(fields.map(([field]) => [field, calcQuartiles(rows.map(r => num(r[field])))]))

function figuresRow(source: Row, fields: Field[], quartiles: Record<string, number[]>, invert: boolean, cell: (value: number, field: string) => string, head: string[]): [string[], Tone[]] {
  const texts = [...head], tones: Tone[] = head.map(() => 'plain')
  for (const [field, less] of fields) {
    const value = num(source[field])
    texts.push(cell(value, field))
    tones.push(quartileTone(value, quartiles[field], less !== invert))
  }
  return [texts, tones]
}

function collect(rows: Array<[string[], Tone[]]>): TableRows {
  return { texts: rows.map(r => r[0]), tones: rows.map(r => r[1]) }
}

/** `build_basic_rows`: the competition's teams (`invert`: the rival table, where a good figure of the team is a bad one). */
export function basicRows(teams: Row[], invert = false): TableRows {
  if (!teams.length) return { texts: [], tones: [] }
  const quartiles = columnQuartiles(teams, BASIC_FIELDS)
  return collect(teams.map(t => figuresRow(t, BASIC_FIELDS, quartiles, invert, v => sf(v), [teamName(t), ...['total_games', 'games_home', 'games_away'].map(k => String(whole(t[k])))])))
}

/** `build_advanced_rows` */
export function advancedRows(teams: Row[], invert = false): TableRows {
  if (!teams.length) return { texts: [], tones: [] }
  const quartiles = columnQuartiles(teams, ADV_FIELDS)
  return collect(teams.map(t => figuresRow(t, ADV_FIELDS, quartiles, invert, v => sf(v), [teamName(t), String(whole(t.total_games))])))
}

/** A team in both halves of a comparison: the stretch (`monthly`, the one that is rated) and the rest of the season. */
export interface Comparative { monthly: Row; rest: Row }

/** `build_comparative_basic_rows`: the stretch with its real difference to the rest, rated among the stretches. */
export function comparativeBasicRows(pairs: Comparative[], invert = false): TableRows {
  if (!pairs.length) return { texts: [], tones: [] }
  const quartiles = columnQuartiles(pairs.map(p => p.monthly), BASIC_FIELDS)
  return collect(pairs.map(({ monthly, rest }) => {
    const [texts, tones] = figuresRow(monthly, BASIC_FIELDS, quartiles, invert, (v, field) => withDiff(v, rest[field]),
      [teamName(monthly), ...['total_games', 'games_home', 'games_away'].map(k => `${whole(monthly[k])}+${whole(rest[k])}`)])
    return [texts, tones]
  }))
}

/** `build_comparative_advanced_rows` */
export function comparativeAdvancedRows(pairs: Comparative[], invert = false): TableRows {
  if (!pairs.length) return { texts: [], tones: [] }
  const quartiles = columnQuartiles(pairs.map(p => p.monthly), ADV_FIELDS)
  return collect(pairs.map(({ monthly, rest }) => figuresRow(monthly, ADV_FIELDS, quartiles, invert, (v, field) => withDiff(v, rest[field]),
    [teamName(monthly), `${whole(monthly.total_games)}+${whole(rest.total_games)}`])))
}

const HIGHER_IS_BETTER = new Set([
  'points_per_game', 'fg2_percentage', 'fg3_percentage', 'ft_percentage', 'efg_percentage', 'true_shooting', 'assists_per_game', 'steals_per_game', 'blocks_per_game', 'offensive_rating',
  'net_rating', 'rebounds_per_game', 'offensive_rebound_rate', 'three_point_rate', 'free_throw_rate', 'assist_fg_rate', 'assist_rate', 'steal_rate', 'block_rate', 'possessions_per_game',
  'total_rebounds', 'rebounds_def', 'rebounds_off', 'assists', 'steals', 'blocks',
])
const LOWER_IS_BETTER = new Set(['defensive_rating', 'turnover_rate', 'turnovers_per_game', 'points_against_per_game', 'points_received', 'turnovers'])

/** `_lm_cell_color`: a game's figure against its rival's in the same game (equal to two decimals is `even`). */
function lastMatchTone(value: number, rival: number, field: string): Tone {
  if (Math.abs(value - rival) < 0.01) return 'even'
  if (HIGHER_IS_BETTER.has(field)) return value > rival ? 'q1' : 'q4'
  if (LOWER_IS_BETTER.has(field)) return value < rival ? 'q1' : 'q4'
  return value > rival ? 'q1' : 'q4'
}

/** `build_last_match_rows`: the two teams of the last game, each cell with the difference to its own season and rated against the rival of that game. */
export function lastMatchRows(selStats: Row, oppStats: Row, selSeason: Row, oppSeason: Row, selName: string, oppName: string): TableRows {
  const side = (stats: Row, rival: Row, season: Row, name: string): [string[], Tone[]] => {
    const texts = [name, '1'], tones: Tone[] = ['plain', 'plain']
    for (const [field] of ADV_FIELDS) {
      const value = num(stats[field])
      tones.push(lastMatchTone(value, num(rival[field]), field))
      texts.push(withDiff(value, season[field]))
    }
    return [texts, tones]
  }
  return collect([side(selStats, oppStats, selSeason, selName), side(oppStats, selStats, oppSeason, oppName)])
}

export type PlayerMode = 'avg' | 'total' | 'projection'

/** `_player_val`: a figure of a player as the table of `mode` shows it (the average, the season total, or the projection to 30 minutes). */
function playerValue(p: Row, field: string, mode: PlayerMode): number {
  const gp = Math.max(whole(p.games_played ?? 0), 1)
  const mpg = Number(p.minutes_per_game ?? 0)
  const n = (key: string) => Number(p[key] ?? 0)
  if (mode === 'total') {
    const totals: Record<string, number> = {
      minutes_per_game: mpg * gp, points_per_game: n('total_pts'), fg1_percentage: n('fg1_percentage'), fg2_percentage: n('fg2_percentage'), fg3_percentage: n('fg3_percentage'),
      total_ro: n('total_ro'), total_rd: n('total_rd'), rebounds_per_game: n('total_rt'), assists_per_game: n('total_assist'), steals_per_game: n('total_st'),
      turnovers_per_game: n('total_to'), blocks_per_game: n('total_bs'), total_pf: n('total_pf'), total_rf: n('total_rf'), pllss_per_game: n('total_pllss'), valoracion_per_game: n('total_val'),
    }
    return totals[field] ?? 0
  }
  if (mode === 'projection') {
    if (field === 'fg1_percentage' || field === 'fg2_percentage' || field === 'fg3_percentage') return n(field)
    if (field === 'minutes_per_game') return 30
    return playerValue(p, field, 'avg') * (mpg > 0 ? 30 / mpg : 0)
  }
  const averages: Record<string, number> = {
    minutes_per_game: mpg, points_per_game: n('points_per_game'), fg1_percentage: n('fg1_percentage'), fg2_percentage: n('fg2_percentage'), fg3_percentage: n('fg3_percentage'),
    total_ro: n('total_ro') / gp, total_rd: n('total_rd') / gp, rebounds_per_game: n('rebounds_per_game'), assists_per_game: n('assists_per_game'),
    steals_per_game: n('steals_per_game'), turnovers_per_game: n('turnovers_per_game'), blocks_per_game: n('blocks_per_game'), total_pf: n('total_pf') / gp, total_rf: n('total_rf') / gp,
    pllss_per_game: n('pllss_per_game'), valoracion_per_game: n('valoracion_per_game'),
  }
  return averages[field] ?? 0
}

/** `build_player_rows`: the headers and the rows of a team's players for the table of `mode`. */
export function playerRows(players: Row[], mode: PlayerMode): TableRows & { headers: string[] } {
  const headers = mode === 'total' ? PLAYER_HEADERS_TOT : PLAYER_HEADERS_AVG
  if (!players.length) return { headers, texts: [], tones: [] }
  const quartiles = Object.fromEntries(PLAYER_FIELDS.map(([field]) => [field, calcQuartiles(players.map(p => playerValue(p, field, mode)))]))
  const rows = players.map((p): [string[], Tone[]] => {
    const texts = [text(p.player_name ?? ''), String(whole(p.games_played ?? 0))], tones: Tone[] = ['plain', 'plain']
    for (const [field, less] of PLAYER_FIELDS) {
      const value = playerValue(p, field, mode)
      texts.push(sf(value))
      tones.push(quartileTone(value, quartiles[field], less))
    }
    return [texts, tones]
  })
  return { headers, ...collect(rows) }
}

/** The coefficients of variation shown in the league's consistency table: header, key and whether a high one is worse (those are rated the other way round). */
const CONSISTENCY_KEYS: Array<[string, string, boolean]> = [
  ['Pts CV%', 'points_per_game', false], ['eFG% CV%', 'efg_percentage', false], ['NR CV%', 'net_rating', false], ['Poss CV%', 'possessions_per_game', false],
  ['TOV% CV%', 'turnover_rate', true], ['3P% CV%', 'fg3_percentage', false],
]
export const CONSISTENCY_HEADERS = ['Equipo', ...CONSISTENCY_KEYS.map(k => k[0])]

export type CVTable = Record<string, Record<string, { cv?: number | null } | undefined>>

/** `build_consistency_rows`: the teams from the most consistent in net rating (lowest CV) to the least, each CV rated among the league's (a low one is good). */
export function consistencyRows(own: CVTable): TableRows {
  const names = Object.keys(own)
  if (!names.length) return { texts: [], tones: [] }
  const cvOf = (stats: CVTable[string], key: string): number | null | undefined => stats[key]?.cv
  const quartiles = Object.fromEntries(CONSISTENCY_KEYS.map(([, key]) => [key, calcQuartiles(names.map(n => cvOf(own[n], key)))]))
  const sorted = [...names].sort((a, b) => (cvOf(own[a], 'net_rating') || 9999) - (cvOf(own[b], 'net_rating') || 9999))          // `cv or 9999`: a zero or a missing one goes last
  return collect(sorted.map((name): [string[], Tone[]] => {
    const texts = [name], tones: Tone[] = ['plain']
    for (const [, key, less] of CONSISTENCY_KEYS) {
      const cv = cvOf(own[name], key)
      texts.push(cv !== null && cv !== undefined ? sf(cv, 1) : '-')
      tones.push(cv !== null && cv !== undefined ? quartileTone(cv, quartiles[key], !less) : 'plain')
    }
    return [texts, tones]
  }))
}
