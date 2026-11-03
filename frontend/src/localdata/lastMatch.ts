// The last game of a team on the device (issue #716, D4c): what `WeeklyReportService._gen_last_match` reads of the team's most recent game, from the rows of the contract. The row of a game
// already carries the figures of the rival and the possessions of the game (the exact ones of `DERIVED` when it has them), so the figures of each side are the table of that one game.
import { aggregateTeams, parsePlayed, type GameRow, type LocalTeamStat } from './aggregateTeams'

export interface LastMatch {
  /** The team's figures in that game, and its rival's (the figures the rival table of the game gives). */
  team: LocalTeamStat
  opponent: LocalTeamStat
  opponentName: string
  /** `dd-mm-yyyy` */
  date: string
}

const two = (n: number) => String(n).padStart(2, '0')

function dayOf(played: number): string {
  const d = new Date(played)
  return `${two(d.getUTCDate())}-${two(d.getUTCMonth() + 1)}-${d.getUTCFullYear()}`
}

/** The team's most recent game with a date that can be read, or `null` if it has none. The rival is the other row of the game; a rival with no row of its own (outside the competition) has no name here. */
export function lastMatchOf(rows: GameRow[], teamName: string): LastMatch | null {
  let last: GameRow | null = null, lastPlayed = -Infinity
  for (const row of rows) {
    if (row.team_name !== teamName) continue
    const played = parsePlayed(row.starttime)
    if (played !== null && played > lastPlayed) { last = row; lastPlayed = played }
  }
  if (!last) return null
  const single = aggregateTeams([last], {})
  const rival = rows.find(r => r.match_id === last!.match_id && r.team_id !== last!.team_id)
  return { team: single.team_stats[0], opponent: single.opponent_stats[0], opponentName: rival?.team_name ?? '', date: dayOf(lastPlayed) }
}
