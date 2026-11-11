// The decisive games of a team (#848): of the matches still to play, those whose result moves the position it is expected to finish in the most, and what each result does to the chance of a cut
// line. Read from the simulated seasons: the average position of the team in those where the home team won against those where it lost. A description of the simulation (it is conditional on how
// the rest of the league goes too), not a promise.
import type { Fixture, SeasonSim } from './seasonSim'

export interface Cut { kind: 'top' | 'bottom'; n: number }

export interface Result {
  /** How many seasons had this result. */
  n: number
  /** The average position of the team in them. */
  meanPosition: number
  /** The chance of being inside the cut line in them; `null` when no line was given or no season had this result. */
  pCut: number | null
}

export interface Decisive {
  fixture: Fixture
  ifHomeWins: Result
  ifAwayWins: Result
  /** Positions the average moves between the two results. */
  swing: number
  involvesTeam: boolean
}

function resultOf(sim: SeasonSim, team: number, fixture: number, outcome: 0 | 1, cut?: Cut): Result {
  const F = sim.remaining.length
  const T = sim.teams.length
  let n = 0
  let sum = 0
  let inside = 0
  for (let s = 0; s < sim.n; s++) {
    if (sim.outcomes[s * F + fixture] !== outcome) continue
    const position = sim.positions[s * T + team]
    n++
    sum += position
    if (cut && (cut.kind === 'top' ? position <= cut.n : position > T - cut.n)) inside++
  }
  return { n, meanPosition: n ? sum / n : NaN, pCut: cut && n ? inside / n : null }
}

/** The matches that move the position of `team` the most, the most first (`limit` of them; `cut` adds what each result does to the chance of the line). */
export function decisiveGames(sim: SeasonSim, team: string, cut?: Cut, limit = 8): Decisive[] {
  const t = sim.teams.indexOf(team)
  if (t < 0) return []
  return sim.remaining
    .map((fixture, f): Decisive => {
      const [ifHomeWins, ifAwayWins] = [resultOf(sim, t, f, 1, cut), resultOf(sim, t, f, 0, cut)]
      return { fixture, ifHomeWins, ifAwayWins, swing: Math.abs(ifAwayWins.meanPosition - ifHomeWins.meanPosition), involvesTeam: fixture.home === team || fixture.away === team }
    })
    .filter(d => Number.isFinite(d.swing) && d.swing > 0)
    .sort((a, b) => b.swing - a.swing)
    .slice(0, limit)
}
