// Evolución on the device (issue #672): `EvolutionService.get_competition_evolution` (`src/services/evolution_service.py`) computed from the rows of the contract.
// Per team, its games in date order give a value of the chosen stat each; at game number i the competition's rolling average is the mean of every team's rolling
// mean over its last `window` games and the cumulative one the mean of every team's running mean (a team with fewer than i games does not count at i).
// Parity with the API: `evolution.test.ts` against `tests/local_vectors/evolution_*.json`.
import type { CompetitionEvolutionPoint } from '@/api/client'
import { parsePlayed, type GameRow } from './aggregateTeams'
import { pyRound } from './pyMath'

/** Every stat the evolution can draw (`EVOLUTION_STAT_KEYS`). */
export const EVOLUTION_STATS = [
  'points', 'points_allowed', 'fg2_made', 'fg2_attempts', 'fg3_made', 'fg3_attempts', 'ft_made', 'ft_attempts', 'rebounds', 'def_rebounds', 'off_rebounds',
  'assists', 'steals', 'turnovers', 'blocks', 'fg2_percentage', 'fg3_percentage', 'ft_percentage', 'possessions', 'offensive_rating', 'defensive_rating',
  'net_rating', 'efg_percentage', 'true_shooting', 'three_point_rate', 'free_throw_rate', 'assist_fg_rate', 'assist_rate', 'turnover_rate', 'steal_rate',
  'block_rate', 'off_rebound_rate', 'def_rebound_rate',
] as const

/** The service counts as an integer what the pipeline gives (`int(val)`, 0 for anything that is not a number). */
const whole = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : 0)

/** Python's `a / b * 100` when `b > 0`, else `null` (the ratio stats have no value without a denominator). */
const ratio = (n: number, d: number): number | null => (d > 0 ? (n / d) * 100 : null)

const estimate = (box: { fga: number; fta: number; tov: number; orb: number }) => Math.max(box.fga + 0.44 * box.fta + box.tov - box.orb, 1)

/**
 * The possessions the service counts in a game: FEB's stored exact count (`DERIVED`) or, if the game has none, the box-score estimate; the published row holds them
 * scaled to 40 minutes, so a game with overtime is brought back to its own length. FBCYL's pipeline never reads `DERIVED`: it always estimates.
 */
function possessionsOf(row: GameRow, own: Parameters<typeof estimate>[0], rival: Parameters<typeof estimate>[0]): { poss: number; oppPoss: number } {
  if (row.fouls !== undefined) return { poss: estimate(own), oppPoss: estimate(rival) }           // only FBCYL rows carry fouls
  const unscale = (row.game_minutes ?? 40) / 40
  return { poss: row.possessions * unscale || estimate(own), oppPoss: row.opponent_possessions * unscale || estimate(rival) }
}

/** The value of a stat in one game of a team, or `null` (`_compute_stat`). */
export function gameValue(row: GameRow, stat: string): number | null {
  const pts = whole(row.points), fg2m = whole(row.fg2_made), fg2a = whole(row.fg2_attempts), fg3m = whole(row.fg3_made), fg3a = whole(row.fg3_attempts)
  const ftm = whole(row.ft_made), fta = whole(row.ft_attempts), drb = whole(row.def_rebounds), orb = whole(row.off_rebounds)
  const ast = whole(row.assists), stl = whole(row.steals), tov = whole(row.turnovers), blk = whole(row.blocks)
  const oppPts = whole(row.opponent_points), oppFg2a = whole(row.opponent_fg2_attempts), oppFg3a = whole(row.opponent_fg3_attempts)
  const oppFta = whole(row.opponent_ft_attempts), oppDrb = whole(row.opponent_def_rebounds), oppOrb = whole(row.opponent_off_rebounds), oppTov = whole(row.opponent_turnovers)
  const fga = fg2a + fg3a, fgm = fg2m + fg3m, oppFga = oppFg2a + oppFg3a
  const { poss, oppPoss } = possessionsOf(row, { fga, fta, tov, orb }, { fga: oppFga, fta: oppFta, tov: oppTov, orb: oppOrb })

  const values: Record<string, number | null> = {
    points: pts, points_allowed: oppPts, fg2_made: fg2m, fg2_attempts: fg2a, fg3_made: fg3m, fg3_attempts: fg3a, ft_made: ftm, ft_attempts: fta,
    rebounds: orb + drb, def_rebounds: drb, off_rebounds: orb, assists: ast, steals: stl, turnovers: tov, blocks: blk,
    fg2_percentage: ratio(fg2m, fg2a), fg3_percentage: ratio(fg3m, fg3a), ft_percentage: ratio(ftm, fta),
    possessions: poss, offensive_rating: (pts / poss) * 100, defensive_rating: (oppPts / oppPoss) * 100, net_rating: (pts / poss) * 100 - (oppPts / oppPoss) * 100,
    efg_percentage: ratio(fgm + 0.5 * fg3m, fga), true_shooting: fga + 0.44 * fta > 0 ? (pts / (2 * (fga + 0.44 * fta))) * 100 : null,
    three_point_rate: ratio(fg3a, fga), free_throw_rate: ratio(fta, fga), assist_fg_rate: ratio(ast, fgm),
    assist_rate: (ast / poss) * 100, turnover_rate: (tov / poss) * 100, steal_rate: (stl / oppPoss) * 100, block_rate: (blk / oppPoss) * 100,
    off_rebound_rate: ratio(orb, orb + oppDrb), def_rebound_rate: ratio(drb, drb + oppOrb),
  }
  const value = values[stat]
  return value === undefined || value === null || Number.isNaN(value) ? null : value
}

/** The games of each team in date order (the day; a game with no readable date goes last, as the pipeline's `"unknown"` does). */
function gamesByTeam(rows: GameRow[]): GameRow[][] {
  const teams = new Map<string, GameRow[]>()
  for (const row of rows) teams.set(row.team_id, [...(teams.get(row.team_id) ?? []), row])
  const day = (row: GameRow) => {
    const t = parsePlayed(row.starttime)
    return t === null ? Infinity : Math.floor(t / 86_400_000)
  }
  return [...teams.values()].map(games => games.map((game, i) => ({ game, i })).sort((a, b) => day(a.game) - day(b.game) || a.i - b.i).map(entry => entry.game))
}

const mean = (values: number[]) => values.reduce((sum, v) => sum + v, 0) / values.length

/** The competition-wide rolling and cumulative averages by game number, or `[]` with no rows. */
export function competitionEvolution(rows: GameRow[], stat: string, window = 5): CompetitionEvolutionPoint[] {
  const teamValues = gamesByTeam(rows).map(games => games.map(game => gameValue(game, stat)))
  const maxGames = Math.max(0, ...teamValues.map(values => values.length))
  const sums = teamValues.map(() => 0), counts = teamValues.map(() => 0)
  const points: CompetitionEvolutionPoint[] = []
  for (let i = 0; i < maxGames; i++) {
    teamValues.forEach((values, t) => {
      const value = i < values.length ? values[i] : null
      if (value !== null) { sums[t] += value; counts[t] += 1 }
    })
    const rolling: number[] = []
    teamValues.forEach(values => {
      if (i >= values.length) return
      const inWindow = values.slice(Math.max(0, i - window + 1), i + 1).filter((v): v is number => v !== null)
      if (inWindow.length > 0) rolling.push(mean(inWindow))
    })
    const cumulative = teamValues.flatMap((values, t) => (counts[t] > 0 && i < values.length ? [sums[t] / counts[t]] : []))
    points.push({
      game_number: i + 1,
      competition_rolling: rolling.length > 0 ? pyRound(mean(rolling), 2) : null,
      competition_cumulative: cumulative.length > 0 ? pyRound(mean(cumulative), 2) : null,
    })
  }
  return points
}
