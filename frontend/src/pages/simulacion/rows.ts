// The rows of the table of the league (issue #850): the table now plus what the simulation expects of every team, best expected position first, and the chance of each cut line the reader drew.
import type { Cut } from '@/forecast/decisive'
import { pBottom, pTop, type SeasonSim } from '@/forecast/seasonSim'

export interface LeagueRow {
  team_id: string
  team_name: string
  position: number
  played: number
  record: string
  diff: number
  expectedWins: number
  meanPosition: number
  pFirst: number
  /** The chance of being inside each cut line, in the order of the lines. */
  cuts: number[]
}

export const cutLabel = (cut: Cut): string => (cut.kind === 'top' ? `Entre los ${cut.n} primeros` : `Entre los ${cut.n} últimos`)

export function leagueRows(sim: SeasonSim, cuts: Cut[]): LeagueRow[] {
  return sim.table
    .map((row): LeagueRow => {
      const t = sim.teams.indexOf(row.team)
      return {
        team_id: row.team, team_name: row.name, position: row.position, played: row.played, record: row.tied ? `${row.won}-${row.lost}-${row.tied}` : `${row.won}-${row.lost}`, diff: row.diff,
        expectedWins: sim.expectedWins[t], meanPosition: sim.meanPosition[t], pFirst: sim.pFirst[t], cuts: cuts.map(c => (c.kind === 'top' ? pTop(sim, t, c.n) : pBottom(sim, t, c.n))),
      }
    })
    .sort((a, b) => a.meanPosition - b.meanPosition || a.position - b.position)
}
