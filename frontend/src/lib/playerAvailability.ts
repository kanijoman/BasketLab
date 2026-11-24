// Who is still in a team and what he has missed (#1082, #1083). The baja is the one of the FEB's «Trayectoria» (published with the images of the team);
// the games he has missed come from the published rows: «did not play» is NO ROW with minutes in that game of his team, which covers a box with 0
// minutes and a box without him alike. The games before his alta never count (a signing for an injured player has not missed what came before him).
import { parsePlayed } from '@/localdata/aggregateTeams'

/** A game of the team (a row of the contract: the id of the match and its start). */
export interface TeamGame { match_id: number | string; starttime: string | null }

export interface Streak { since: string; games: number }

const pad = (n: number) => String(n).padStart(2, '0')

/** `dd-mm-yyyy` of UTC milliseconds. */
const dayOf = (t: number) => { const d = new Date(t); return `${pad(d.getUTCDate())}-${pad(d.getUTCMonth() + 1)}-${d.getUTCFullYear()}` }

/**
 * The current streak: the most recent consecutive games of his team he has not played, and the day of the first of them; `null` when he played the last one
 * (or the team has no dated game, or his alta `yyyy-mm-dd` is after the last game). The games before the alta are left out; the one of the day of the alta counts.
 */
export function missedStreak(teamGames: TeamGame[], playedIds: ReadonlySet<number | string>, alta: string | null): Streak | null {
  const from = alta ? Date.parse(`${alta}T00:00:00Z`) : -Infinity
  const dated = teamGames
    .map(g => ({ id: String(g.match_id), at: parsePlayed(g.starttime) }))
    .filter((g): g is { id: string; at: number } => g.at !== null)
    .sort((a, b) => b.at - a.at)                                              // newest first
  const mine = new Set([...playedIds].map(String))
  let streak = 0, first = 0
  for (const g of dated) {
    if (g.at < from) break                                                    // before his alta: nothing he could have played
    if (mine.has(g.id)) break
    streak += 1
    first = g.at
  }
  return streak ? { since: dayOf(first), games: streak } : null
}

/** The sentence the technical staff reads in the notes. */
export const missedNote = (name: string, streak: Streak): string =>
  `${name} llega desde ${streak.since} sin jugar (${streak.games} ${streak.games === 1 ? 'partido' : 'partidos'})`

/** `true` when the baja `yyyy-mm-dd` of his line is already reached (the day of the baja he is out); no line, no baja or a baja to come: he stays. */
export function hasLeftTeam(extra: { baja?: string | null } | undefined, today: Date): boolean {
  const baja = extra?.baja
  return !!baja && baja <= today.toISOString().slice(0, 10)
}

/** What the individual scouting of a team says of who has been missing (#1083): `{player_id: sentence}` for the players of `teamId` with a current streak. `playerRows` are the FEB rows of the contract
 * (one per player and game WITH minutes); FBCYL has no rows of this shape and no alta, so it has no notes. */
export function staffNotes(
  roster: Array<{ player_id: string | number; player_name?: string | null }>, teamId: string,
  teamRows: Array<TeamGame & { team_id: string }>, playerRows: Array<{ match_id: number | string; player_id: string; team_id: string }>,
  images: { players: Record<string, { alta?: string | null }> } | null,
): Record<string, string> {
  const games = teamRows.filter(g => String(g.team_id) === String(teamId))
  const notes: Record<string, string> = {}
  for (const player of roster) {
    const id = String(player.player_id)
    const played = new Set(playerRows.filter(r => String(r.team_id) === String(teamId) && String(r.player_id) === id).map(r => r.match_id))
    const streak = missedStreak(games, played, images?.players[id]?.alta ?? null)
    if (streak) notes[id] = missedNote(player.player_name ?? '—', streak)
  }
  return notes
}
