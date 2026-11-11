// The simulation of the league (#848): the matches still to play of the REAL calendar, played thousands of times, and the table ranked each time (`standings`: a generic tie-break; the promotion,
// play-off and relegation rules change with the competition and the season, so none is modelled: the page counts positions and lets the reader draw the cut lines).
//
// Each season draws the strength of every team ONCE from what the Kalman rating knows of it (mean and variance), so the games of a team are correlated: a team that turns out to be good wins
// more of its games. Each match is then played from those strengths plus the home court of the family, with the spread of a game minus what the ratings are already unsure of, so that the
// result of one match is still as spread as the model validated for the win probability. The ratings come from the results of the calendar too (they can be newer than the archive).
import type { Calendar } from '@/webdata/calendar'
import { matchupPace, type GameResult } from './gameLog'
import type { ForecastModel } from './pool'
import { hashSeed, mulberry32, normalSampler } from './prng'
import { addResult, cloneLeague, newLeague, rankLeague, standingsOf, type StandingRow } from './standings'
import { NOISE } from './teamRatings'
import { headline, wpParams } from './winProb'

export const SIMULATIONS = 10000

export interface Fixture {
  code: string
  round: number
  /** `YYYY-MM-DDTHH:MM`, Madrid time. */
  start: string | null
  home: string
  away: string
  homeName: string
  awayName: string
  kind: 'scheduled' | 'live'
}

export interface SeasonSim {
  n: number
  teams: string[]
  names: Record<string, string>
  /** The table now. */
  table: StandingRow[]
  remaining: Fixture[]
  /** Per team, in how many seasons it finished in each position (index 0 is first). */
  positionCounts: Uint32Array[]
  expectedWins: number[]
  meanPosition: number[]
  pFirst: number[]
  /** Per season and remaining match: 1 the home team won, 0 the away team did, 2 a tie (only where the group allows it). */
  outcomes: Uint8Array
  /** Per season and team: the position it finished in. */
  positions: Uint8Array
}

/** The spread of one simulated match: that of a game of the family minus what the two ratings are unsure of, never under the noise of a game (12 points). */
export const gameSpread = (sigma: number, varHome: number, varAway: number): number => Math.sqrt(Math.max(sigma * sigma - varHome - varAway, NOISE))

/** The matches of the calendar still to play (`live` ones too), leaving out any the games already have. */
export function pendingFixtures(games: GameResult[], calendar: Calendar): Fixture[] {
  const played = new Set(games.map(g => g.id))
  return calendar.matches
    .filter(m => (m.kind === 'scheduled' || m.kind === 'live') && !played.has(m.match_id))
    .map((m): Fixture => ({ code: m.code, round: m.round, start: m.start, home: String(m.home.id), away: String(m.away.id), homeName: m.home.name, awayName: m.away.name, kind: m.kind as Fixture['kind'] }))
}

/** The chance of finishing in the first `k` positions / in the last `k`. */
export const pTop = (sim: SeasonSim, team: number, k: number): number => sim.positionCounts[team].slice(0, Math.max(0, k)).reduce((a, b) => a + b, 0) / sim.n
export const pBottom = (sim: SeasonSim, team: number, k: number): number => (k <= 0 ? 0 : sim.positionCounts[team].slice(-k).reduce((a, b) => a + b, 0) / sim.n)

export function simulateSeason(model: ForecastModel, calendar: Calendar, { n = SIMULATIONS, seed = calendar.collection }: { n?: number; seed?: string } = {}): SeasonSim {
  const remaining = pendingFixtures(model.games, calendar)
  const names: Record<string, string> = {}
  for (const g of model.games) { names[g.home] = g.homeName; names[g.away] = g.awayName }
  for (const f of remaining) { names[f.home] = f.homeName; names[f.away] = f.awayName }
  const teams = Object.keys(names).sort()
  const T = teams.length
  const base = newLeague(teams)
  for (const g of model.games) addResult(base, base.index.get(g.home)!, base.index.get(g.away)!, g.margin, g.tied)

  const { sigma } = wpParams(model.gender)
  const sd = teams.map(t => Math.sqrt(model.ratings.variance(t)))
  const ties = calendar.ties_allowed
  const plan = remaining.map(f => {
    const [h, a] = [base.index.get(f.home)!, base.index.get(f.away)!]
    const mu = headline({ ratings: model.ratings, own: f.home, rival: f.away, court: 'own', pace: matchupPace(model.games, f.home, f.away), gender: model.gender }).mu
    return { h, a, mu, spread: gameSpread(sigma, model.ratings.variance(f.home), model.ratings.variance(f.away)) }
  })

  const uniform = mulberry32(hashSeed(seed))
  const normal = normalSampler(uniform)
  const positionCounts = teams.map(() => new Uint32Array(T))
  const winsSum = new Float64Array(T)
  const outcomes = new Uint8Array(n * remaining.length)
  const positions = new Uint8Array(n * T)
  const strength = new Float64Array(T)
  const draw = new Float64Array(T)
  for (let s = 0; s < n; s++) {
    const league = cloneLeague(base)
    for (let t = 0; t < T; t++) strength[t] = sd[t] * normal()
    plan.forEach((m, f) => {
      let margin = Math.round(m.mu + strength[m.h] - strength[m.a] + m.spread * normal())
      const tie = margin === 0 && ties
      if (margin === 0 && !ties) margin = uniform() < 0.5 ? 1 : -1                  // an overtime decides it, as the win probability assumes: 50/50
      addResult(league, m.h, m.a, margin, tie)
      outcomes[s * remaining.length + f] = tie ? 2 : margin > 0 ? 1 : 0
    })
    for (let t = 0; t < T; t++) draw[t] = uniform()
    const position = rankLeague(league, draw)
    for (let t = 0; t < T; t++) {
      positionCounts[t][position[t] - 1]++
      positions[s * T + t] = position[t]
      winsSum[t] += league.wins2[t] / 2
    }
  }
  const meanPosition = teams.map((_, t) => positionCounts[t].reduce((sum, c, i) => sum + c * (i + 1), 0) / n)
  return {
    n, teams, names, table: standingsOf(model.games, teams), remaining, positionCounts, outcomes, positions, meanPosition,
    expectedWins: Array.from(winsSum, w => w / n), pFirst: positionCounts.map(c => c[0] / n),
  }
}
