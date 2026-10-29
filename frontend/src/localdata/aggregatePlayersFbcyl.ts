// The FBCYL player table computed on the device from the rows of the contract (issue #644): one row per player and game played, with the identity
// already resolved by the exporter (`player_uuid`: the uuid FBCYL left out of some games is completed over the whole season, the phantom players are
// not there, `pllss` is the plus-minus of the game). Summed by `(player_uuid, team_id)` with the formulas of `FBCYLPipelineBuilder.build_player_stats_pipeline`
// and enriched with the advanced figures of `PlayerStatsService._enrich_with_advanced_stats`. Parity with the API is enforced by
// `aggregatePlayersFbcyl.test.ts` against `tests/local_vectors/players_fbcyl.json`.
import type { PlayerStat } from '@/api/client'
import { aggregateTeams, matchesFilters, type GameRow, type TeamTableFilter } from './aggregateTeams'
import { advancedFigures, ZERO_ADVANCED, type PlayerTableFilter } from './aggregatePlayers'

/** One player in one game he played (minutes as FBCYL gives them: whole minutes, not seconds). */
export interface FbcylPlayerGameRow {
  match_id: number | string
  player_uuid: string; player_id: number | string; player_name: string; team_id: number | string; team_name: string
  starttime: string | null
  is_local: boolean; won: boolean; tied: boolean
  minutes: number
  p1m: number; p1a: number; p2m: number; p2a: number; p3m: number; p3a: number
  pts: number; assist: number; ro: number; rd: number; rt: number; st: number; to: number; bs: number; pf: number; rf: number; pllss: number; val: number
}

const SUMMED = ['p1m', 'p1a', 'p2m', 'p2a', 'p3m', 'p3a', 'pts', 'assist', 'ro', 'rd', 'rt', 'st', 'to', 'bs', 'pf', 'rf', 'pllss', 'val'] as const

const pct = (n: number, d: number) => (d > 0 ? (n / d) * 100 : 0)
const perGame = (n: number, games: number) => (games > 0 ? n / games : 0)

function season(games: FbcylPlayerGameRow[]): PlayerStat {
  const [first] = games
  const s = Object.fromEntries(SUMMED.map(k => [k, games.reduce((n, g) => n + g[k], 0)])) as Record<(typeof SUMMED)[number], number>
  const minutes = games.reduce((n, g) => n + g.minutes, 0)
  const n = games.length
  const fga = s.p2a + s.p3a
  const tsa = s.p2a + s.p3a + 0.44 * s.p1a
  const ts = tsa > 0 ? (s.pts / (2 * tsa)) * 100 : 0
  const efg = pct(s.p2m + s.p3m + 0.5 * s.p3m, fga)                         // sic: the pipeline adds the threes twice
  const threePr = pct(s.p3a, fga)
  const ftr = pct(s.p1a, fga)
  const ppg = perGame(s.pts, n), mpg = perGame(minutes, n), apg = perGame(s.assist, n), spg = perGame(s.st, n), bpg = perGame(s.bs, n)
  const tpg = perGame(s.to, n), vpg = perGame(s.val, n)
  return {
    player_uuid: first.player_uuid, player_id: first.player_id, player_name: first.player_name, team_name: first.team_name, team_id: first.team_id,
    games_played: n, total_minutes: minutes, minutes_per_game: mpg,
    total_p1m: s.p1m, total_p1a: s.p1a, total_p2m: s.p2m, total_p2a: s.p2a, total_p3m: s.p3m, total_p3a: s.p3a,
    total_pts: s.pts, total_assist: s.assist, total_as: s.assist, total_ro: s.ro, total_rd: s.rd, total_rt: s.rt, total_st: s.st, total_to: s.to,
    total_bs: s.bs, total_bl: s.bs, total_pf: s.pf, total_rf: s.rf, total_pllss: s.pllss, total_val: s.val,
    fg1_percentage: pct(s.p1m, s.p1a), ft_percentage: pct(s.p1m, s.p1a), fg2_percentage: pct(s.p2m, s.p2a), fg3_percentage: pct(s.p3m, s.p3a),
    points_per_game: ppg, ppg, mpg, assists_per_game: apg, ast_pg: apg, rebounds_per_game: perGame(s.rt, n), steals_per_game: spg, stl_pg: spg,
    blocks_per_game: bpg, blk_pg: bpg, turnovers_per_game: tpg, tov_pg: tpg, valoracion_per_game: vpg, val_pg: vpg, pllss_per_game: perGame(s.pllss, n),
    ts, efg, three_pr: threePr, ftr, true_shooting: ts, efg_percentage: efg, three_point_rate: threePr, free_throw_rate: ftr,
    ast_pct: pct(s.assist, fga), tov_pct: pct(s.to, fga), stl_pct: pct(s.st, fga), blk_pct: pct(s.bs, fga),
    orb_pct: pct(s.ro, s.ro + s.rd), drb_pct: pct(s.rd, s.ro + s.rd),
    usage: n > 0 ? ((fga + 0.44 * s.p1a + s.to) / (n * 100)) * 100 : 0,
    orating: tsa > 0 ? (s.pts / tsa) * 100 : 0,
    drating: s.st + s.bs > 0 ? 120 - ((s.st + s.bs) / n) * 5 : 120,
  } as unknown as PlayerStat
}

/**
 * The answer of `GET /players/{collection}` for an FBCYL competition without a server. `teamRows` are the games of the whole season (the context of
 * the advanced figures never depends on the filter); the order is team name, then points, as the pipeline sorts. The API builds that context from
 * the opponent table it repeats from the team's own (bug #642), and so does this: the advanced figures keep parity with what the API shows today.
 */
export function aggregatePlayersFbcyl(rows: FbcylPlayerGameRow[], teamRows: GameRow[], filter: PlayerTableFilter): PlayerStat[] {
  const groups = new Map<string, FbcylPlayerGameRow[]>()
  for (const r of rows) {
    if (!matchesFilters(r, filter as TeamTableFilter) || (filter.team !== undefined && r.team_name !== filter.team)) continue
    const key = JSON.stringify([r.player_uuid, r.team_id])
    groups.set(key, [...(groups.get(key) ?? []), r])
  }
  const players = [...groups.values()].map(season)
  if (players.length) {
    const tables = aggregateTeams(teamRows, {}).team_stats
    const byId = new Map(tables.map(t => [String(t.team_id), t]))
    for (const p of players) {
      const team = byId.get(String(p.team_id))
      Object.assign(p, team ? advancedFigures(p, team, team) : ZERO_ADVANCED)
    }
  }
  return players.sort((a, b) => (a.team_name < b.team_name ? -1 : a.team_name > b.team_name ? 1 : (b.total_pts as number) - (a.total_pts as number)))
}
