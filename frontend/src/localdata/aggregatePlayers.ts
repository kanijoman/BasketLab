// Player tables computed on the device from the rows of the contract (issue #327): one row per player and game played
// (`build_season_player_rows_pipeline`), summed with the formulas of `pipeline_player_stats.py` and enriched with the advanced figures
// (`PlayerStatsService._enrich_with_advanced_stats`: from the WHOLE season's team context, whatever the filter). Parity with the API is enforced
// by `aggregatePlayers.test.ts` against `tests/local_vectors/players_feb.json`.
import type { PlayerStat } from '@/api/client'
import { aggregateTeams, matchesFilters, parsePlayed, type GameRow, type LocalTeamStat, type TeamTableFilter } from './aggregateTeams'
import * as adv from './advancedStats'
import { pyRound } from './pyMath'

/** One player in one game he played (minutes in seconds, FEB's box score). */
export interface PlayerGameRow {
  match_id: number | string
  player_id: string; player_name: string; team_id: string; team_name: string
  starttime: string | null
  is_local: boolean; won: boolean
  minutes: number; pllss: number
  p1m: number; p1a: number; p2m: number; p2a: number; p3m: number; p3a: number
  pts: number; assist: number; ro: number; rd: number; rt: number; st: number; to: number; bs: number; pf: number; rf: number; val: number
}

/** The filters of `GET /players/{collection}`: those of the team tables plus one team (by name). */
export type PlayerTableFilter = TeamTableFilter & { team?: string }

const SUMMED = ['p1m', 'p1a', 'p2m', 'p2a', 'p3m', 'p3a', 'pts', 'assist', 'ro', 'rd', 'rt', 'st', 'to', 'bs', 'pf', 'rf', 'pllss', 'val'] as const

const pct = (n: number, d: number) => (d > 0 ? (n / d) * 100 : 0)
const perGame = (n: number, games: number) => (games > 0 ? n / games : 0)
/** The shooting rates are `null` (not 0) when there are no field-goal attempts, as in the pipeline. */
const rate = (n: number, d: number) => (d > 0 ? (n / d) * 100 : null)

/** The rows of a player in play order (a game whose date cannot be read goes first, as in the pipeline's sort); ties keep the order of the rows. */
const chronological = (games: PlayerGameRow[]) => [...games].sort((a, b) => (parsePlayed(a.starttime) ?? -Infinity) - (parsePlayed(b.starttime) ?? -Infinity))

function season(unsorted: PlayerGameRow[]): PlayerStat {
  const games = chronological(unsorted)
  const last = games[games.length - 1]                       // the name and the team name shown are those of his LAST game (#652)
  const sums = Object.fromEntries(SUMMED.map(k => [k, games.reduce((n, g) => n + g[k], 0)])) as Record<(typeof SUMMED)[number], number>
  const seconds = games.reduce((n, g) => n + g.minutes, 0)
  const n = games.length
  const fgAtt = sums.p2a + sums.p3a
  const tsaDen = fgAtt + 0.44 * sums.p1a
  return {
    player_id: last.player_id, player_name: last.player_name, team_name: last.team_name, team_id: last.team_id,
    games_played: n, total_minutes: seconds > 0 ? seconds / 60 : 0, minutes_per_game: n > 0 ? seconds / 60 / n : 0,
    total_p1m: sums.p1m, total_p1a: sums.p1a, total_p2m: sums.p2m, total_p2a: sums.p2a, total_p3m: sums.p3m, total_p3a: sums.p3a,
    total_pts: sums.pts, total_assist: sums.assist, total_ro: sums.ro, total_rd: sums.rd, total_rt: sums.rt, total_st: sums.st,
    total_to: sums.to, total_bs: sums.bs, total_pf: sums.pf, total_rf: sums.rf, total_pllss: sums.pllss, total_val: sums.val,
    fg1_percentage: pct(sums.p1m, sums.p1a), fg2_percentage: pct(sums.p2m, sums.p2a), fg3_percentage: pct(sums.p3m, sums.p3a),
    points_per_game: perGame(sums.pts, n), assists_per_game: perGame(sums.assist, n), rebounds_per_game: perGame(sums.rt, n),
    steals_per_game: perGame(sums.st, n), blocks_per_game: perGame(sums.bs, n), turnovers_per_game: perGame(sums.to, n),
    valoracion_per_game: perGame(sums.val, n), pllss_per_game: perGame(sums.pllss, n),
    offensive_rebounds_per_game: perGame(sums.ro, n), defensive_rebounds_per_game: perGame(sums.rd, n), fouls_per_game: perGame(sums.pf, n),
    efg_percentage: rate(sums.p2m + 1.5 * sums.p3m, fgAtt), true_shooting: tsaDen > 0 ? (sums.pts / (2 * tsaDen)) * 100 : null,
    free_throw_rate: rate(sums.p1a, fgAtt), three_point_rate: rate(sums.p3a, fgAtt),
    turnover_rate: tsaDen + sums.to > 0 ? (sums.to / (tsaDen + sums.to)) * 100 : null,
  } as unknown as PlayerStat
}

// What the service gives a player whose team it finds no context for (`_default_adv`): zeros under the keys of the normal path (#647).
export const ZERO_ADVANCED = {
  usage_pct: 0, orating: 0, drating: 0, net_rtg: 0, ast_pct: 0, tov_pct_adv: 0, stl_pct: 0, blk_pct: 0, drb_pct: 0, orb_pct: 0, pie: 0,
}

export function advancedFigures(p: PlayerStat, team: LocalTeamStat, opp: LocalTeamStat) {
  const totals = p as unknown as Record<string, number>
  const t = team as unknown as Record<string, number>
  const o = opp as unknown as Record<string, number>
  return {
    usage_pct: pyRound(adv.usagePercentage(totals, t), 1),
    orating: pyRound(adv.offensiveRating(totals, t, o), 1), drating: pyRound(adv.defensiveRating(totals, t, o), 1),
    net_rtg: pyRound(adv.netRating(totals, t, o), 1),
    ast_pct: pyRound(adv.assistPercentage(totals, t), 1), tov_pct_adv: pyRound(adv.turnoverPercentage(totals), 1),
    stl_pct: pyRound(adv.stealPercentage(totals, t, o), 1), blk_pct: pyRound(adv.blockPercentage(totals, t, o), 1),
    drb_pct: pyRound(adv.reboundPercentage(totals, t, o, false), 1), orb_pct: pyRound(adv.reboundPercentage(totals, t, o, true), 1),
    pie: pyRound(adv.pie(totals, t, o), 2),
  }
}

/**
 * The answer of `GET /players/{collection}` without a server. `teamRows` are the games of the whole season (the context of the advanced
 * figures never depends on the filter); the order is team name, then points, as the pipeline sorts.
 */
export function aggregatePlayers(rows: PlayerGameRow[], teamRows: GameRow[], filter: PlayerTableFilter): PlayerStat[] {
  const groups = new Map<string, PlayerGameRow[]>()
  for (const r of rows) {
    if (!matchesFilters(r, filter) || (filter.team !== undefined && r.team_name !== filter.team)) continue
    const key = JSON.stringify([r.player_id, r.team_id])                      // the identity: the player within the team; names are not part of it (#652)
    groups.set(key, [...(groups.get(key) ?? []), r])
  }
  const players = [...groups.values()].map(season)
  if (players.length) {
    const tables = aggregateTeams(teamRows, {})
    const teams = new Map(tables.team_stats.map(t => [String(t.team_id), t]))
    const opponents = new Map(tables.opponent_stats.map(t => [String(t.team_id), t]))
    for (const p of players) {
      const team = teams.get(String(p.team_id))
      const opp = opponents.get(String(p.team_id))
      Object.assign(p, team && opp ? advancedFigures(p, team, opp) : ZERO_ADVANCED)
    }
  }
  return players.sort((a, b) => (a.team_name < b.team_name ? -1 : a.team_name > b.team_name ? 1 : (b.total_pts as number) - (a.total_pts as number)))
}
