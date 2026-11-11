// The table of a league and the way its ties are broken (#848). A GENERIC tie-break, like the federation's but not recursive (the real one re-ranks sub-groups of the tied; the bases of each
// competition differ and change with the season, so none is modelled): wins (a tie is half a win), then among the tied teams the games between them (wins, then point difference), then the point
// difference of the whole league, then a draw. In the simulation only margins are drawn, so the points scored by each team are not known and do not decide.
import type { GameResult } from './gameLog'

/** The state a table is ranked from. Wins are in half units (a win is 2, a tie 1), so they stay integers. */
export interface LeagueState {
  teams: string[]
  index: Map<string, number>
  wins2: Int32Array
  /** Point difference of each team over the whole league. */
  diff: Float64Array
  /** What team `i` got against team `j` (`i * n + j`): half wins and point difference. */
  h2hW: Int32Array
  h2hD: Float64Array
}

export function newLeague(teams: string[]): LeagueState {
  const n = teams.length
  return { teams, index: new Map(teams.map((t, i) => [t, i])), wins2: new Int32Array(n), diff: new Float64Array(n), h2hW: new Int32Array(n * n), h2hD: new Float64Array(n * n) }
}

export const cloneLeague = (s: LeagueState): LeagueState => ({ ...s, wins2: s.wins2.slice(), diff: s.diff.slice(), h2hW: s.h2hW.slice(), h2hD: s.h2hD.slice() })

/** One result: `margin` = home minus away points; a tied game is half a win for each. */
export function addResult(s: LeagueState, home: number, away: number, margin: number, tie: boolean): void {
  const n = s.teams.length
  const [wh, wa] = tie ? [1, 1] : margin > 0 ? [2, 0] : [0, 2]
  s.wins2[home] += wh
  s.wins2[away] += wa
  s.diff[home] += margin
  s.diff[away] -= margin
  s.h2hW[home * n + away] += wh
  s.h2hW[away * n + home] += wa
  s.h2hD[home * n + away] += margin
  s.h2hD[away * n + home] -= margin
}

/** The position (1 is first) of each team, given a draw (lower first) for what nothing else tells apart. */
export function rankLeague(s: LeagueState, draw: ArrayLike<number>): Int32Array {
  const n = s.teams.length
  const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => s.wins2[b] - s.wins2[a] || a - b)
  for (let i = 0; i < n;) {
    let j = i
    while (j < n && s.wins2[order[j]] === s.wins2[order[i]]) j++
    if (j - i > 1) sortTied(s, order, i, j, draw)
    i = j
  }
  const positions = new Int32Array(n)
  order.forEach((team, k) => { positions[team] = k + 1 })
  return positions
}

function sortTied(s: LeagueState, order: number[], from: number, to: number, draw: ArrayLike<number>): void {
  const n = s.teams.length
  const group = order.slice(from, to)
  const among = (team: number, table: ArrayLike<number>): number => group.reduce((sum, other) => sum + (other === team ? 0 : table[team * n + other]), 0)
  const key = new Map(group.map(t => [t, [among(t, s.h2hW), among(t, s.h2hD), s.diff[t], draw[t]]]))
  group.sort((a, b) => {
    const [x, y] = [key.get(a)!, key.get(b)!]
    return y[0] - x[0] || y[1] - x[1] || y[2] - x[2] || x[3] - y[3] || a - b
  })
  group.forEach((team, k) => { order[from + k] = team })
}

export interface StandingRow {
  team: string
  name: string
  played: number
  won: number
  lost: number
  tied: number
  pf: number
  pa: number
  diff: number
  position: number
}

/** The table of the results so far, in order. Ties that nothing tells apart go by the order of the ids, so the table is always the same. */
export function standingsOf(games: GameResult[], extraTeams: string[] = []): StandingRow[] {
  const names = new Map<string, string>()
  for (const g of games) { names.set(g.home, g.homeName); names.set(g.away, g.awayName) }
  const teams = [...new Set([...names.keys(), ...extraTeams])].sort()
  const state = newLeague(teams)
  const rows = new Map(teams.map((team): [string, StandingRow] => [team, { team, name: names.get(team) ?? team, played: 0, won: 0, lost: 0, tied: 0, pf: 0, pa: 0, diff: 0, position: 0 }]))
  for (const g of games) {
    addResult(state, state.index.get(g.home)!, state.index.get(g.away)!, g.margin, g.tied)
    for (const [team, pf, pa] of [[g.home, g.homePoints, g.awayPoints], [g.away, g.awayPoints, g.homePoints]] as const) {
      const r = rows.get(team)!
      r.played++
      r.pf += pf
      r.pa += pa
      r.diff += pf - pa
      if (g.tied) r.tied++
      else if (pf > pa) r.won++
      else r.lost++
    }
  }
  const positions = rankLeague(state, teams.map((_, i) => i))
  for (const [team, row] of rows) row.position = positions[state.index.get(team)!]
  return [...rows.values()].sort((a, b) => a.position - b.position)
}
