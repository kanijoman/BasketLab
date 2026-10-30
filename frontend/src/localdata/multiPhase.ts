// Multifase on the device (issue #671): `MultiPhaseService` (`src/services/multi_phase_service.py`) and `CollectionService.get_sibling_collections` in the browser.
// The tables of several collections (the phases of a competition) are merged by team or player name: the counting stats are added up, the per-game figures,
// percentages and ratings are recomputed from the totals. Every quirk of the service is kept on purpose (what it does not add is seeded with 0 and what is not
// a number comes from the first row), because the page must show what the API shows. Parity: `multiPhase.test.ts` against `tests/local_vectors/multi_phase.json`.
import { pyRound } from './pyMath'

type Row = Record<string, unknown>

/** Fields that are simple totals (added across phases). */
const SUM_FIELDS = [
  'games_played', 'games_won', 'games_lost', 'points_scored', 'points_received', 'fg2_made', 'fg2_attempts', 'fg3_made', 'fg3_attempts', 'ft_made', 'ft_attempts',
  'rebounds_off', 'rebounds_def', 'total_rebounds', 'assists', 'steals', 'turnovers', 'blocks', 'personal_fouls', 'total_possessions', 'total_minutes',
  'total_points', 'valoracion',
] as const

/** Per-game fields and the (total, games) pair they come from. */
const PER_GAME: Record<string, [string, string]> = {
  points_per_game: ['points_scored', 'games_played'], points_against_per_game: ['points_received', 'games_played'],
  possessions_per_game: ['total_possessions', 'games_played'], rebounds_per_game: ['total_rebounds', 'games_played'],
  assists_per_game: ['assists', 'games_played'], steals_per_game: ['steals', 'games_played'], turnovers_per_game: ['turnovers', 'games_played'],
  blocks_per_game: ['blocks', 'games_played'],
  total_points_per_game: ['total_points', 'games_played'], minutes_per_game: ['total_minutes', 'games_played'], valoracion_per_game: ['valoracion', 'games_played'],
}

const PERCENTAGES: Record<string, [string, string]> = {
  fg2_percentage: ['fg2_made', 'fg2_attempts'], fg3_percentage: ['fg3_made', 'fg3_attempts'], ft_percentage: ['ft_made', 'ft_attempts'],
}

/** Fields that name the entity: kept from its first row, never seeded with 0 (the web draws the crest of a team from `team_id`). */
const IDENTITY = new Set(['_id', 'team_id', 'player_id'])

/** The names FEB's pipelines give, and the canonical ones the merge uses. */
const FEB_ALIASES: Record<string, string> = {
  total_games: 'games_played', fg2_attempted: 'fg2_attempts', fg3_attempted: 'fg3_attempts', ft_attempted: 'ft_attempts',
  total_pts: 'total_points', total_p2m: 'fg2_made', total_p2a: 'fg2_attempts', total_p3m: 'fg3_made', total_p3a: 'fg3_attempts', total_p1m: 'ft_made', total_p1a: 'ft_attempts',
  total_ro: 'rebounds_off', total_rd: 'rebounds_def', total_rt: 'total_rebounds', total_assist: 'assists', total_st: 'steals', total_to: 'turnovers', total_bs: 'blocks',
  total_pf: 'personal_fouls', total_val: 'valoracion',
}

/** Python's `x or 0` for a figure: a missing, null or zero value is 0. */
const orZero = (value: unknown): number => (typeof value === 'number' && value ? value : 0)
const present = (value: unknown) => value !== undefined && value !== null
const round2 = (x: number) => pyRound(x, 2)

/** A copy of the row with the FEB names renamed to the canonical ones (only where the canonical name is not already there). */
function normalised(row: Row): Row {
  const out: Row = { ...row }
  for (const [from, to] of Object.entries(FEB_ALIASES)) {
    if (from in out && !(to in out)) { out[to] = out[from]; delete out[from] }
  }
  return out
}

/** The per-game figures, percentages and ratings of a merged row, from its summed totals. */
function recomputeDerived(row: Row): void {
  const games = orZero(row.games_played)
  for (const [field, [totalField, gamesField]] of Object.entries(PER_GAME)) {
    const total = row[totalField]
    const g = orZero(row[gamesField]) || games
    if (present(total) && g) row[field] = round2(Number(total) / g)
  }

  // player rows use total_points instead of points_scored
  if ('total_points' in row && !('points_per_game' in row)) {
    const total = orZero(row.total_points)
    if (games && total) row.points_per_game = round2(total / games)
  } else if ('total_points' in row && games) {
    row.points_per_game = round2(orZero(row.total_points) / games)
  }

  if ('points_per_game' in row) row.points_allowed_per_game = row.points_against_per_game ?? 0

  for (const [field, [madeField, attemptsField]] of Object.entries(PERCENTAGES)) {
    const made = orZero(row[madeField]), attempts = orZero(row[attemptsField])
    row[field] = attempts ? round2((made / attempts) * 100) : 0
  }

  const played = orZero(row.games_played), won = orZero(row.games_won)
  row.win_percentage = played ? round2((won / played) * 100) : 0
  row.total_games = games

  const orb = orZero(row.rebounds_off), drb = orZero(row.rebounds_def)
  if (games) {
    row.offensive_rebounds_per_game = round2(orb / games)
    row.defensive_rebounds_per_game = round2(drb / games)
  }

  const fg2m = orZero(row.fg2_made), fg2a = orZero(row.fg2_attempts), fg3m = orZero(row.fg3_made), fg3a = orZero(row.fg3_attempts), fta = orZero(row.ft_attempts)
  const fgm = fg2m + fg3m, fga = fg2a + fg3a
  const tov = orZero(row.turnovers), ast = orZero(row.assists), stl = orZero(row.steals), blk = orZero(row.blocks)
  const pts = orZero(row.points_scored) || orZero(row.total_points)
  const poss = orZero(row.total_possessions), oppPts = orZero(row.points_received)

  if (poss) {
    row.offensive_rating = round2((pts / poss) * 100)
    row.defensive_rating = round2((oppPts / poss) * 100)
    row.net_rating = round2(((pts - oppPts) / poss) * 100)
  }
  if (fga) {
    row.efg_percentage = round2(((fg2m + 1.5 * fg3m) / fga) * 100)
    row.three_point_rate = round2((fg3a / fga) * 100)
  }
  const tovDenominator = fga + 0.44 * fta + tov
  if (tovDenominator) row.turnover_rate = round2((tov / tovDenominator) * 100)
  if (fga) row.free_throw_rate = round2((fta / fga) * 100)
  const tsDenominator = 2 * (fga + 0.44 * fta)
  if (tsDenominator && pts) row.true_shooting = round2((pts / tsDenominator) * 100)
  if (fgm) row.assist_fg_rate = round2((ast / fgm) * 100)
  if (poss) {
    row.assist_rate = round2((ast / poss) * 100)
    row.steal_rate = round2((stl / poss) * 100)
    row.block_rate = round2((blk / poss) * 100)
  }
  const rebounds = orb + drb
  if (rebounds) {
    row.offensive_rebound_rate = round2((orb / rebounds) * 100)
    row.defensive_rebound_rate = round2((drb / rebounds) * 100)
  }
}

/**
 * One merged row per entity (`key` is `team_name` or `player_name`) over the tables of the collections, in the order the entities first appear. The tables are not
 * modified. An entity with no name is skipped.
 */
export function mergeByKey(tablesByCollection: Record<string, Row[]>, key: string): Row[] {
  const merged = new Map<string, Row>()
  for (const table of Object.values(tablesByCollection)) {
    for (const source of table) {
      const row = normalised(source)
      const entity = row[key]
      if (!entity) continue
      const name = String(entity)
      let acc = merged.get(name)
      if (!acc) {
        // seeded from the first row: the numbers start at 0 (but the identity), what is not a number stays as it is
        acc = Object.fromEntries(Object.entries(row).map(([k, v]) => [k, (typeof v === 'number' || typeof v === 'boolean') && !IDENTITY.has(k) ? 0 : v]))
        acc[key] = name
        merged.set(name, acc)
      }
      for (const field of SUM_FIELDS) if (field in row) acc[field] = (typeof acc[field] === 'number' ? (acc[field] as number) : 0) + orZero(row[field])
    }
  }
  const rows = [...merged.values()]
  rows.forEach(recomputeDerived)
  return rows
}

// ── The phases of a competition (CollectionService.get_sibling_collections) ─────────────────────────────────────────────

const YEAR = /^\d{4}$/
const GROUP = /^[A-Z0-9]{1,2}$/i
const FBCYL_PREFIX = /^FBCYL_/i

/** Best-effort parsing of the competition and the season of a collection name (`_parse_components`): FBCYL `FBCYL_{competition}_{season}`, FEB a slug with the year(s) of the season. */
function parseComponents(name: string, league: 'FEB' | 'FBCYL'): { competition: string; season: string } {
  if (league === 'FBCYL') {
    const rest = name.replace(FBCYL_PREFIX, '')
    const cut = rest.indexOf('_')
    return cut < 0 ? { competition: rest, season: '' } : { competition: rest.slice(0, cut), season: rest.slice(cut + 1).replace(/_/g, ' ') }
  }
  const parts = name.split('_')
  const yearAt = parts.findIndex(p => YEAR.test(p))
  if (yearAt < 0) return { competition: name, season: '' }
  const remainder = parts.slice(yearAt)
  // a short last token (A, B, 1A…) is the group; a longer phase name (ELIMINATORIAS, FASE_ASCENSO) stays in the season
  const season = remainder.length > 1 && GROUP.test(remainder[remainder.length - 1]) ? remainder.slice(0, -1).join('_') : remainder.join('_')
  return { competition: parts.slice(0, yearAt).join('_'), season }
}

/** Only the leading year token(s) of a season (`2025_ELIMINATORIAS` → `2025`), or the whole season when it has none. */
function seasonYear(season: string): string {
  const years: string[] = []
  for (const part of season.split('_')) {
    if (!YEAR.test(part)) break
    years.push(part)
  }
  return years.join('_') || season
}

/** The collections of the pool that share the competition and season of `name` (the group or phase suffix is ignored), sorted; `name` is always one of them. */
export function siblingCollections(name: string, pool: string[]): string[] {
  const league = (n: string) => (FBCYL_PREFIX.test(n) ? 'FBCYL' : 'FEB')
  const ref = parseComponents(name, league(name))
  const siblings = pool.filter(other => {
    if (league(other) !== league(name)) return false
    const parsed = parseComponents(other, league(other))
    return parsed.competition === ref.competition && seasonYear(parsed.season) === seasonYear(ref.season)
  })
  if (!siblings.includes(name)) siblings.push(name)
  return siblings.sort()
}
