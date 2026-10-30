// Combinaciones on the device (issue #686): the lineup tables of a team from the per-game counters a competition publishes (`lineups/` of web-data), as
// `LineupService.get_lineup_analysis` answers them. The service computes every combination game by game and merges the games of the period summing the counters and recomputing the
// ratios (`repository_lineup._merge_lineup_stats`), so that is what is done here, with its roundings and its oddities (the ORB% of a lineup stays that of its first game).
// Parity: `lineups.test.ts` against `tests/local_vectors/lineups_*.json`.
import type { GameLogEntry, LineupRow } from '@/api/client'
import { npMean, npStd, pyRound } from './pyMath'

/** What the exporter publishes of a competition (`export_lineups`). */
export interface Lineups {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  columns: string[]
  teams: LineupTeam[]
}

export interface LineupTeam {
  team_id: string
  team_name: string
  /** The games of the team with play-by-play, in the order of the collection: the day they are logged with and the instant MongoDB reads (`null`: unreadable, out of any period). */
  games: { date: string; at: string | null }[]
  /** `id → [name, photo]` */
  players: Record<string, [string, string | null]>
  /** Per size: `[player ids (sorted), one row per game the lineup played]` */
  sizes: Record<string, [string[], number[][]][]>
}

export interface LineupQuery {
  size: number
  stat?: string
  /** Days back from `now` (0 or none: the whole season). */
  period?: number
  lastGame?: boolean
  includeGameLog?: boolean
  minMinutes?: number
  minGames?: number
  now?: Date
}

/** Statistics where lower is better (`LineupService.REVERSE_STATS`). */
const LOWER_IS_BETTER = new Set(['drtg', 'tov_pct'])
const DAY_MS = 86_400_000

type Counters = Record<string, number>

const COUNTERS = ['points_for', 'points_against', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta', 'orb', 'drb', 'ast', 'stl', 'blk', 'tov', 'pf'] as const

/** The row of one game, by column name. */
function named(columns: string[], row: number[]): Counters {
  return Object.fromEntries(columns.map((column, i) => [column, row[i]]))
}

/** The ratios of one game from its counters (`LineupStatsCalculator._calculate_final_stats`): ORtg, DRtg and ORB% are the game's own (they need the opponent's figures). */
function gameStats(game: Counters): Counters {
  const { fga, fgm, fg3m, fta, tov } = game
  const denominator = fga + 0.44 * fta + tov
  return {
    ...game,
    plus_minus: game.points_for - game.points_against,
    net_rating: pyRound(game.ortg - game.drtg, 1),
    efg_pct: fga > 0 ? pyRound(((fgm + 0.5 * fg3m) / fga) * 100, 1) : 0,
    tov_pct: denominator > 0 ? pyRound((tov / denominator) * 100, 1) : 0,
    ftr: fga > 0 ? pyRound(fta / fga, 2) : 0,
    trb: game.orb + game.drb,
  }
}

/** The fields of a lineup of the API, in the order the calculator writes them. */
const FIELDS = ['points_for', 'points_against', 'plus_minus', 'possessions', 'ortg', 'drtg', 'net_rating', 'efg_pct', 'tov_pct', 'orb_pct', 'ftr', 'fgm', 'fga', 'fg3m', 'fg3a', 'ftm', 'fta',
  'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'minutes', 'games_played', 'segments_count', 'avg_minutes_per_game'] as const

const pick = (stats: Counters): Counters => Object.fromEntries(FIELDS.map(field => [field, stats[field]]))

/** The merge of the games of a lineup (`_merge_lineup_stats`): sums, and ratios recomputed when the sums allow it (otherwise the first game's are kept, as the service does). */
function merged(games: Counters[]): Counters {
  const total: Counters = { ...gameStats(games[0]), games_played: 1, segments_count: games[0].segments, avg_minutes_per_game: games[0].minutes }
  for (const game of games.slice(1)) {
    for (const name of [...COUNTERS, 'minutes', 'possessions']) total[name] += game[name]
    total.games_played += 1
    total.segments_count += game.segments
  }
  if (games.length === 1) return pick(total)
  total.trb = total.orb + total.drb
  total.avg_minutes_per_game = pyRound(total.minutes / total.games_played, 1)
  total.plus_minus = total.points_for - total.points_against
  if (total.possessions > 0) {
    total.ortg = pyRound((total.points_for / total.possessions) * 100, 1)
    total.drtg = pyRound((total.points_against / total.possessions) * 100, 1)
    total.net_rating = pyRound(total.ortg - total.drtg, 1)
  }
  if (total.fga > 0) {
    total.efg_pct = pyRound(((total.fgm + 0.5 * total.fg3m) / total.fga) * 100, 1)
    total.ftr = pyRound(total.fta / total.fga, 2)
  }
  const denominator = total.fga + 0.44 * total.fta + total.tov
  if (denominator > 0) total.tov_pct = pyRound((total.tov / denominator) * 100, 1)
  return pick(total)                                                                            // orb_pct: the first game's (as the service)
}

/** One line of the game log of a lineup (before merging: the figures of that game alone). */
function logEntry(date: string, game: Counters): GameLogEntry {
  const stats = gameStats(game)
  return {
    date, net_rating: stats.net_rating, ortg: stats.ortg, drtg: stats.drtg, plus_minus: stats.plus_minus, points_for: stats.points_for, points_against: stats.points_against,
    efg_pct: stats.efg_pct, tov_pct: stats.tov_pct, orb_pct: stats.orb_pct, ftr: stats.ftr, ast: stats.ast, trb: stats.trb, minutes: stats.minutes,
  }
}

/** The games of the team the query looks at (`get_games_for_team` with the date filter, or `get_last_game_for_team`): their indexes in `team.games`. */
function gamesOf(team: LineupTeam, query: LineupQuery): number[] {
  const dated = team.games.flatMap((game, index) => (game.at === null ? [] : [{ index, time: Date.parse(`${game.at}Z`) }]))
  if (query.lastGame) {
    const last = dated.reduce<{ index: number; time: number } | null>((best, game) => (best === null || game.time > best.time ? game : best), null)
    return last ? [last.index] : []
  }
  if (query.period && query.period > 0) {
    const cutoff = (query.now ?? new Date()).getTime() - query.period * DAY_MS
    return dated.filter(game => game.time >= cutoff).map(game => game.index)
  }
  return team.games.map((_, index) => index)
}

/** The IFQ of a lineup: the mean of its net ratings per game over their (population) standard deviation; none with fewer than 3 games or no spread. */
function ifq(log: GameLogEntry[]): number | null {
  if (log.length < 3) return null
  const values = log.map(entry => entry.net_rating)
  const std = npStd(values)
  return std > 0 ? pyRound(npMean(values) / std, 2) : null
}

/** `GET /lineups/{collection}/{team_id}`: the lineups of a team of the given size, sorted by `stat`; `null` when the team is not in the publication (the API answers). */
export function lineupAnalysis(published: Lineups, teamId: string, query: LineupQuery): LineupRow[] | null {
  const team = published.teams.find(t => t.team_id === String(teamId))
  if (!team) return null
  const games = gamesOf(team, query)
  if (games.length === 0) return []
  const inPeriod = new Set(games)
  const narrowed = Boolean(query.lastGame || (query.period && query.period > 0))
  const minMinutes = query.minMinutes ?? 15
  const minGames = narrowed ? Math.min(query.minGames ?? 5, games.length) : (query.minGames ?? 5)

  const rows: LineupRow[] = []
  for (const [ids, perGame] of team.sizes[String(query.size)] ?? []) {
    const played = perGame.map(row => named(published.columns, row)).filter(game => inPeriod.has(game.game))
    if (played.length === 0) continue
    const stats = merged(played)
    if (stats.minutes < minMinutes || stats.games_played < minGames) continue
    const log = played.map(game => logEntry(team.games[game.game].date, game))
    const names = ids.map(id => team.players[id]?.[0] ?? `Player ${id}`)
    rows.push({
      ...stats, players: names, player_names: names, player_ids: ids, player_photo_urls: ids.map(id => team.players[id]?.[1] ?? null),
      ifq: ifq(log), ...(query.includeGameLog ? { game_log: log } : {}),
    } as unknown as LineupRow)
  }
  // The repository sorts by net rating and the service by the chosen statistic, both stable (ties keep the order of the one before)
  rows.sort((a, b) => b.net_rating - a.net_rating)
  const stat = query.stat ?? 'net_rating'
  const value = (row: LineupRow): number => (row[stat] as number | null | undefined) || 0
  return rows.sort(LOWER_IS_BETTER.has(stat) ? (a, b) => value(a) - value(b) : (a, b) => value(b) - value(a))
}
