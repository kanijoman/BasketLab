// Team tables computed on the device from the rows of the contract (issue #327): one row per team and game
// (`AggregationPipelineBuilder.build_season_rows_pipeline`), summed with the same filters and formulas as the Mongo pipelines
// (`pipeline_team_stats.py`, `pipeline_opponent_stats.py`, `basic_stats.py`, `advanced_stats.py`). Parity with the API is enforced by
// `aggregateTeams.test.ts` against `tests/local_vectors/team_stats_feb.json`.
import type { TeamStat } from '@/api/client'

/** What the season `$group` reads of a team in a game, with the figures of its rival and the date (`dd-mm-yyyy - hh:mm`, as FEB writes it). */
export interface GameRow {
  match_id: number | string
  team_id: string
  team_name: string
  starttime: string | null
  is_local: boolean
  won: boolean
  points: number
  opponent_points: number
  fg2_made: number; fg2_attempts: number; fg3_made: number; fg3_attempts: number; ft_made: number; ft_attempts: number
  def_rebounds: number; off_rebounds: number
  assists: number; steals: number; turnovers: number; blocks: number
  possessions: number
  opponent_fg2_made: number; opponent_fg2_attempts: number; opponent_fg3_made: number; opponent_fg3_attempts: number
  opponent_ft_made: number; opponent_ft_attempts: number
  opponent_def_rebounds: number; opponent_off_rebounds: number
  opponent_assists: number; opponent_steals: number; opponent_turnovers: number; opponent_blocks: number
  opponent_possessions: number
  // FBCYL only: it reports total rebounds and fouls, and a game can end tied (neither won nor lost)
  tied?: boolean
  total_rebounds?: number; fouls?: number; opponent_total_rebounds?: number; opponent_fouls?: number
}

/** The filters of `GET /teams/{collection}`; `from` / `to` are `YYYY-MM-DD`: from the start of the first day to the END of the last one (a game of the `to` day is in, #643). */
export interface TeamTableFilter {
  venue?: 'home' | 'away'
  result?: 'won' | 'lost'
  from?: string
  to?: string
}

/** A team's season totals and ratios, the row the pages already read (`TeamStat`) plus the games counted. */
export type LocalTeamStat = TeamStat & { match_list: Array<GameRow['match_id']> }

export interface TeamTables {
  team_stats: LocalTeamStat[]
  opponent_stats: LocalTeamStat[]
}

/** The measured figures of one side of a game: the team's own, or (rival tables) what its opponent did against it. */
interface Side {
  points: number; received: number
  fg2m: number; fg2a: number; fg3m: number; fg3a: number; ftm: number; fta: number
  def: number; off: number; oppDef: number; oppOff: number
  assists: number; steals: number; turnovers: number; blocks: number
  possessions: number; oppPossessions: number
  reb: number; fouls: number
}

const own = (r: GameRow): Side => ({
  points: r.points, received: r.opponent_points,
  fg2m: r.fg2_made, fg2a: r.fg2_attempts, fg3m: r.fg3_made, fg3a: r.fg3_attempts, ftm: r.ft_made, fta: r.ft_attempts,
  def: r.def_rebounds, off: r.off_rebounds, oppDef: r.opponent_def_rebounds, oppOff: r.opponent_off_rebounds,
  assists: r.assists, steals: r.steals, turnovers: r.turnovers, blocks: r.blocks,
  possessions: r.possessions, oppPossessions: r.opponent_possessions,
  reb: r.total_rebounds ?? 0, fouls: r.fouls ?? 0,
})

// The rival pipeline inverts the perspective: the rival's figures are the measured ones and the team's own become the `opponent_*` references.
const rival = (r: GameRow): Side => ({
  points: r.opponent_points, received: r.points,
  fg2m: r.opponent_fg2_made, fg2a: r.opponent_fg2_attempts, fg3m: r.opponent_fg3_made, fg3a: r.opponent_fg3_attempts,
  ftm: r.opponent_ft_made, fta: r.opponent_ft_attempts,
  def: r.opponent_def_rebounds, off: r.opponent_off_rebounds, oppDef: r.def_rebounds, oppOff: r.off_rebounds,
  assists: r.opponent_assists, steals: r.opponent_steals, turnovers: r.opponent_turnovers, blocks: r.opponent_blocks,
  possessions: r.opponent_possessions, oppPossessions: r.possessions,
  reb: r.opponent_total_rebounds ?? 0, fouls: r.opponent_fouls ?? 0,
})

const SUMMED = ['points', 'received', 'fg2m', 'fg2a', 'fg3m', 'fg3a', 'ftm', 'fta', 'def', 'off', 'oppDef', 'oppOff',
  'assists', 'steals', 'turnovers', 'blocks', 'possessions', 'oppPossessions', 'reb', 'fouls'] as const

/** `safe_divide`: a zero denominator gives 0, never NaN or Infinity. */
const div = (n: number, d: number) => (d === 0 ? 0 : n / d)
const pct = (n: number, d: number) => div(n, d) * 100

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/**
 * The date of a game as UTC milliseconds, or `null` if it cannot be read (`onError: null`). FEB writes `dd-mm-yyyy - hh:mm` (to the minute);
 * FBCYL writes `Oct 4, 2025 7:00:00 PM` and its pipelines keep only the day (midnight); the `to` day is in for both leagues (#643).
 */
export function parsePlayed(starttime: string | null | undefined): number | null {
  const text = starttime ?? ''
  const feb = /^(\d{2})-(\d{2})-(\d{4}) - (\d{2}):(\d{2})$/.exec(text)
  const fbcyl = /^([A-Za-z]{3}) (\d{1,2}), (\d{4})/.exec(text)
  let d: number, mo: number, y: number, h = 0, mi = 0
  if (feb) [, d, mo, y, h, mi] = feb.map(Number)
  else if (fbcyl && MONTHS.includes(fbcyl[1])) [d, mo, y] = [Number(fbcyl[2]), MONTHS.indexOf(fbcyl[1]) + 1, Number(fbcyl[3])]
  else return null
  const t = Date.UTC(y, mo - 1, d, h, mi)
  const back = new Date(t)
  return back.getUTCDate() === d && back.getUTCMonth() === mo - 1 ? t : null          // 31-02-2025 is not a date
}

/** The bound `YYYY-MM-DD` (or ISO datetime) as UTC milliseconds, as Python's `datetime.fromisoformat` + pymongo give it. */
const bound = (iso: string) => Date.parse(/T|\s/.test(iso) ? iso : `${iso}T00:00:00Z`)

/** The first instant AFTER the day `to` (`YYYY-MM-DD`): the API's upper bound is the end of that day (bug #643); a bound with a time is used as given. */
const endOfDay = (to: string) => (/T|\s/.test(to) ? bound(to) + 1 : bound(to) + 86_400_000)

/** Whether a game (a team's or a player's row) passes the venue, result and date filters. */
export function matchesFilters(r: Pick<GameRow, 'is_local' | 'won' | 'starttime' | 'tied'>, f: TeamTableFilter): boolean {
  if (f.venue && r.is_local !== (f.venue === 'home')) return false
  if (f.result === 'won' && !r.won) return false
  if (f.result === 'lost' && (r.won || r.tied)) return false           // a tied game (FBCYL) is neither
  if (f.from || f.to) {
    const t = parsePlayed(r.starttime)
    if (t === null) return false                                  // a null date matches no range in Mongo
    if (f.from && t < bound(f.from)) return false
    if (f.to && t >= endOfDay(f.to)) return false
  }
  return true
}

type Sums = Record<(typeof SUMMED)[number], number>

function derive(id: string, name: string, games: number, home: number, matches: GameRow['match_id'][], s: Sums, fbcyl: boolean): LocalTeamStat {
  const fga = s.fg2a + s.fg3a
  const reb = fbcyl ? s.reb : s.def + s.off                       // FBCYL reports its own total of rebounds
  const ortg = s.possessions === 0 ? 0 : (s.points / s.possessions) * 100
  const drtg = s.oppPossessions === 0 ? 0 : (s.received / s.oppPossessions) * 100
  return {
    _id: id, team_id: id, team_name: name,
    total_games: games, games_home: home, games_away: games - home,
    points_scored: s.points, points_received: s.received,
    fg2_made: s.fg2m, fg2_attempted: s.fg2a, fg3_made: s.fg3m, fg3_attempted: s.fg3a, ft_made: s.ftm, ft_attempted: s.fta,
    rebounds_def: s.def, rebounds_off: s.off, opponent_rebounds_def: s.oppDef, opponent_rebounds_off: s.oppOff,
    assists: s.assists, steals: s.steals, turnovers: s.turnovers, blocks: s.blocks,
    total_possessions: s.possessions, opponent_possessions: s.oppPossessions, match_list: matches,
    total_rebounds: reb,
    points_per_game: s.points / games, points_against_per_game: s.received / games, points_allowed_per_game: s.received / games,
    possessions_per_game: s.possessions / games, rebounds_per_game: reb / games,
    offensive_rebounds_per_game: s.off / games, defensive_rebounds_per_game: s.def / games,
    assists_per_game: s.assists / games, steals_per_game: s.steals / games, turnovers_per_game: s.turnovers / games, blocks_per_game: s.blocks / games,
    fg2_percentage: pct(s.fg2m, s.fg2a), fg3_percentage: pct(s.fg3m, s.fg3a), ft_percentage: pct(s.ftm, s.fta),
    efg_percentage: pct(s.fg2m + 1.5 * s.fg3m, fga), turnover_rate: pct(s.turnovers, s.possessions),
    offensive_rebound_rate: pct(s.off, s.off + s.oppDef), free_throw_rate: pct(s.fta, fga),
    three_point_rate: pct(s.fg3a, fga), true_shooting: pct(s.points, 2 * (fga + 0.44 * s.fta)),
    assist_fg_rate: pct(s.assists, s.fg2m + s.fg3m),
    assist_rate: div(s.assists * 100, s.possessions), steal_rate: div(s.steals * 100, s.possessions), block_rate: div(s.blocks * 100, s.possessions),
    defensive_rebound_rate: pct(s.def, s.def + s.oppOff),
    offensive_rating: ortg, defensive_rating: drtg, net_rating: fbcyl || s.possessions !== 0 ? ortg - drtg : 0,
  }
}

/** What only FBCYL's team table has: fouls, wins and losses, the rival's shooting as `opp_*` and the names it gives the rebounds per game. */
function fbcylExtras(rows: GameRow[], s: Sums, rival: boolean): Record<string, number> {
  const sum = (pick: (r: GameRow) => number | undefined) => rows.reduce((n, r) => n + (pick(r) ?? 0), 0)
  const games = rows.length
  const won = rows.filter(r => r.won).length
  return {
    fouls: s.fouls, games_played: games, games_won: won, games_lost: rows.filter(r => !r.won && !r.tied).length, win_pct: pct(won, games),
    fg_percentage: pct(s.fg2m + s.fg3m, s.fg2a + s.fg3a), pace: s.possessions / games,
    def_rebounds_per_game: s.def / games, off_rebounds_per_game: s.off / games,
    // `opp_*` are the references of the table: the rival's figures in the team's table and the team's own in the rival's (#642)
    opp_fg2_made: sum(r => (rival ? r.fg2_made : r.opponent_fg2_made)), opp_fg2_attempted: sum(r => (rival ? r.fg2_attempts : r.opponent_fg2_attempts)),
    opp_fg3_made: sum(r => (rival ? r.fg3_made : r.opponent_fg3_made)), opp_fg3_attempted: sum(r => (rival ? r.fg3_attempts : r.opponent_fg3_attempts)),
    opp_ft_attempted: sum(r => (rival ? r.ft_attempts : r.opponent_ft_attempts)), opp_turnovers: sum(r => (rival ? r.turnovers : r.opponent_turnovers)),
  }
}

function table(rows: GameRow[], side: (r: GameRow) => Side): LocalTeamStat[] {
  const groups = new Map<string, GameRow[]>()
  for (const r of rows) groups.set(r.team_id, [...(groups.get(r.team_id) ?? []), r])
  const out = [...groups.entries()].map(([id, games]) => {
    const sums = Object.fromEntries(SUMMED.map(k => [k, 0])) as Sums
    for (const g of games) for (const k of SUMMED) sums[k] += side(g)[k]
    const fbcyl = games[0].fouls !== undefined
    const stat = derive(id, games[0].team_name, games.length, games.filter(g => g.is_local).length, games.map(g => g.match_id), sums, fbcyl)
    return fbcyl ? { ...stat, ...fbcylExtras(games, sums, side === rival) } : stat
  })
  return out.sort((a, b) => (b.points_per_game as number) - (a.points_per_game as number))
}

/**
 * `{team_stats, opponent_stats}` of the rows that pass the filter: the answer of `GET /teams/{collection}` without a server. FBCYL rows (they
 * carry `fouls`) get FBCYL's table; its `opponent_stats` is the REAL rival, not the copy of the team's own table the API gives today (#642).
 */
export function aggregateTeams(rows: GameRow[], filter: TeamTableFilter): TeamTables {
  const kept = rows.filter(r => matchesFilters(r, filter))
  return { team_stats: table(kept, own), opponent_stats: table(kept, rival) }
}
