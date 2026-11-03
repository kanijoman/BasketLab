// The quartiles of the players on the device (issue #707): `PlayerStatsService.get_quartiles` over the player table of the competition. For each of 15 per-game fields, the
// players with at least three games and a figure; four or more values give `{min, q1, q2, q3, max, count}`, NOT rounded (`np.percentile`, linear). Parity: `playerQuartiles.test.ts`
// against `tests/local_vectors/player_quartiles.json`.
import type { PlayerStat } from '@/api/client'

const FIELDS = ['points_per_game', 'rebounds_per_game', 'offensive_rebounds_per_game', 'defensive_rebounds_per_game', 'assists_per_game', 'steals_per_game', 'turnovers_per_game',
  'blocks_per_game', 'fouls_per_game', 'valoracion_per_game', 'pllss_per_game', 'minutes_per_game', 'fg1_percentage', 'fg2_percentage', 'fg3_percentage'] as const

const MIN_GAMES = 3
const MIN_VALUES = 4

/** `np.percentile(values, 100 * q)` with the default (linear) method over sorted values. numpy interpolates from the nearer end (`a + d·t` below the half, `b − d·(1 − t)` from it),
 *  and the two differ in the last digit, so this is not the textbook `a + d·t`. */
export function percentile(sorted: number[], q: number): number {
  const virtual = (sorted.length - 1) * q
  const previous = Math.floor(virtual)
  const next = Math.min(previous + 1, sorted.length - 1)
  const t = virtual - previous
  const a = sorted[previous]
  const b = sorted[next]
  const diff = b - a
  return t >= 0.5 ? b - diff * (1 - t) : a + diff * t
}

export type PlayerQuartiles = Record<string, { min: number; q1: number; q2: number; q3: number; max: number; count: number }>

export function playerQuartiles(players: PlayerStat[]): PlayerQuartiles {
  const out: PlayerQuartiles = {}
  for (const field of FIELDS) {
    const values = players
      .filter(player => ((player as unknown as Record<string, unknown>)[field] ?? null) !== null && (((player as unknown as Record<string, number>).games_played) ?? 0) >= MIN_GAMES)
      .map(player => Number((player as unknown as Record<string, unknown>)[field]))
      .sort((a, b) => a - b)
    if (values.length >= MIN_VALUES) {
      out[field] = { min: values[0], q1: percentile(values, 0.25), q2: percentile(values, 0.5), q3: percentile(values, 0.75), max: values[values.length - 1], count: values.length }
    }
  }
  return out
}
