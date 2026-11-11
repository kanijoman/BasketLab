// The games of a competition as the forecast reads them (#847): the two rows of each match paired into ONE game (home, away, margin, pace) in the order they were played, plus the results the
// calendar has and the archive does not yet. Everything the models need hangs from here: the Kalman ratings (home, away, margin, in order), the pace of a matchup and, for the scenarios, the
// box score of each side. Ids are texts (FBCYL has numbers in its rows).
import { parsePlayed, type GameRow } from '@/localdata/aggregateTeams'
import type { Calendar } from '@/webdata/calendar'
import { boxOf, possessions } from './factors'
import { pyRound } from '@/localdata/pyMath'
import { TeamRatings } from './teamRatings'

export interface GameResult {
  /** The `match_id` of the game (the `_id` of its document): the same id the calendar gives a match. */
  id: string
  /** When it was played, UTC milliseconds; `null` when the date cannot be read (those go last) and for a result that only the calendar has. */
  played: number | null
  home: string
  away: string
  homeName: string
  awayName: string
  /** Points of each side and the home team's minus the away team's. */
  homePoints: number
  awayPoints: number
  margin: number
  /** FBCYL games can end tied. */
  tied: boolean
  /** Possessions per 40 minutes of the game (the mean of both sides); `null` for a result that only the calendar has (no box score). */
  pace: number | null
  source: 'rows' | 'calendar'
  homeRow?: GameRow
  awayRow?: GameRow
}

/** The pace of a game from the row of one side: the mean possessions of both sides (FEB rows carry them per 40 minutes), or the estimate FGA - ORB + TOV + 0.44 FTA when the row has none. */
export function gamePace(row: GameRow): number | null {
  if (row.possessions > 0 && row.opponent_possessions > 0) return (row.possessions + row.opponent_possessions) / 2
  const estimate = (possessions(boxOf(row, 'own')) + possessions(boxOf(row, 'opp'))) / 2
  return estimate > 0 ? estimate : null
}

function pair(rows: GameRow[]): Map<string, GameRow[]> {
  const byMatch = new Map<string, GameRow[]>()
  for (const row of rows) {
    const key = String(row.match_id)
    byMatch.set(key, [...(byMatch.get(key) ?? []), row])
  }
  return byMatch
}

function fromRows(id: string, [a, b]: GameRow[]): GameResult | null {
  if (!a || !b || String(a.team_id) === String(b.team_id) || a.is_local === b.is_local) return null      // one row, or it does not say who is at home: not a game
  const [home, away] = a.is_local ? [a, b] : [b, a]
  return {
    id, played: parsePlayed(home.starttime), home: String(home.team_id), away: String(away.team_id), homeName: home.team_name, awayName: away.team_name,
    homePoints: home.points, awayPoints: home.opponent_points, margin: home.points - home.opponent_points, tied: Boolean(home.tied), pace: gamePace(home), source: 'rows', homeRow: home, awayRow: away,
  }
}

const byPlay = (x: GameResult, y: GameResult): number =>
  (x.played ?? Infinity) - (y.played ?? Infinity) || (x.id < y.id ? -1 : x.id > y.id ? 1 : 0) || 0

/**
 * The games in the order they were played: those of the rows by date, then the results of the calendar that the rows do not have (finished matches the archive has not loaded yet, so they are the
 * newest) by round. A match being played (`live`) or still to play is not a result.
 */
export function buildGames(rows: GameRow[], calendar?: Calendar | null): GameResult[] {
  const games = [...pair(rows)].map(([id, pairRows]) => fromRows(id, pairRows)).filter((g): g is GameResult => g !== null).sort(byPlay)
  if (!calendar) return games
  const known = new Set(games.map(g => g.id))
  const extra = calendar.matches
    .filter(m => m.kind === 'result' && m.score && !known.has(m.match_id))
    .sort((x, y) => x.round - y.round || (x.code < y.code ? -1 : 1))
    .map((m): GameResult => ({
      id: m.match_id, played: null, home: String(m.home.id), away: String(m.away.id), homeName: m.home.name, awayName: m.away.name,
      homePoints: m.score![0], awayPoints: m.score![1], margin: m.score![0] - m.score![1], tied: m.score![0] === m.score![1], pace: null, source: 'calendar',
    }))
  return [...games, ...extra]
}

/** The Kalman ratings after all the games, in order. */
export function buildRatings(games: GameResult[]): TeamRatings {
  const ratings = new TeamRatings()
  for (const g of games) ratings.update(g.home, g.away, g.margin)
  return ratings
}

export const gamesOf = (games: GameResult[], team: string): GameResult[] => games.filter(g => g.home === String(team) || g.away === String(team))

/** The possessions per 40 minutes of the matchup: the mean of the paces of the games of both teams (a game between them counts twice), to one decimal; 0 when neither has a pace. */
export function matchupPace(games: GameResult[], a: string, b: string): number {
  const paces = [...gamesOf(games, a), ...gamesOf(games, b)].map(g => g.pace).filter((p): p is number => p !== null)
  return paces.length ? pyRound(paces.reduce((sum, p) => sum + p, 0) / paces.length, 1) : 0
}
