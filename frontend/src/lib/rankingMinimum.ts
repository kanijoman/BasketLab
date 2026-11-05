// The minimum volume to appear in a ranking (issue #763). A rate (a shooting percentage, a rating, an average per game) is falsified by whoever has almost no volume behind
// it: a 100 % on two attempts leads the ranking of threes. The rule is the SAME for every statistic and relative to the competition, like the rest of the thresholds of the web:
// a player qualifies when his volume reaches at least HALF OF THE MEDIAN volume per game of the team (the games his team has played), the median taken over the players of the
// competition with at least three games. Volume is what the statistic is made of: the attempts of its category for the shooting percentages, the minutes for everything else.
import type { PlayerStat } from '@/api/client'

/** The share of the median volume that is the minimum (agreed on 05/11/2026). */
export const SHARE_OF_MEDIAN = 0.5
/** The players that make the median: with fewer games their volume says little about what a normal one is. */
export const MEDIAN_MIN_GAMES = 3

export type VolumeKind = 'minutes' | 'p1a' | 'p2a' | 'p3a' | 'fga' | 'tsa'

interface VolumeDef {
  /** What the minimum counts, to say it on the page. */
  unit: string
  /** The volume of a player; 0 when the data do not say (then the median is 0 and nobody is left out). */
  of: (player: PlayerStat) => number
}

const num = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0)
const fieldGoals = (p: PlayerStat) => num(p.total_p2a) + num(p.total_p3a)

export const VOLUME: Record<VolumeKind, VolumeDef> = {
  minutes: { unit: 'minutos', of: p => (typeof p.total_minutes === 'number' ? p.total_minutes : num(p.minutes_per_game) * num(p.games_played)) },
  p1a: { unit: 'intentos de tiro libre', of: p => num(p.total_p1a) },
  p2a: { unit: 'intentos de 2', of: p => num(p.total_p2a) },
  p3a: { unit: 'intentos de triple', of: p => num(p.total_p3a) },
  fga: { unit: 'tiros de campo', of: fieldGoals },
  /** The shots that count for the true shooting: the field goals and 0.44 of the free throws. */
  tsa: { unit: 'tiros (campo y libres)', of: p => fieldGoals(p) + 0.44 * num(p.total_p1a) },
}

const teamOf = (p: PlayerStat) => String(p.team_id ?? p.team_name)

/** The games each team has played: those of its player who played the most (a player of the rotation plays them all). */
export function teamGamesOf(players: PlayerStat[]): Map<string, number> {
  const games = new Map<string, number>()
  for (const p of players) games.set(teamOf(p), Math.max(games.get(teamOf(p)) ?? 0, num(p.games_played)))
  return games
}

const median = (values: number[]): number => {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const middle = sorted.length >> 1
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

export interface Minimum {
  /** The minimum volume per game of the team. */
  perTeamGame: number
  /** Whether a player reaches it with the games his team has played. */
  qualifies: (player: PlayerStat) => boolean
}

/** The minimum of the competition (`players` are all of it, not the filtered ones) for the statistics made of `kind`. Players that never shot count in the median. */
export function minimumFor(players: PlayerStat[], kind: VolumeKind): Minimum {
  const volume = VOLUME[kind].of
  const teamGames = teamGamesOf(players)
  const perGame = (p: PlayerStat) => volume(p) / (teamGames.get(teamOf(p)) || 1)
  const perTeamGame = SHARE_OF_MEDIAN * median(players.filter(p => num(p.games_played) >= MEDIAN_MIN_GAMES).map(perGame))
  return { perTeamGame, qualifies: p => volume(p) + 1e-9 >= perTeamGame * (teamGames.get(teamOf(p)) || 1) }
}
