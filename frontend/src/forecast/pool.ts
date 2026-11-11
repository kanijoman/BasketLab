// The model of a competition the preview is made from (#847): the Kalman ratings, the level of every team (the four factors it makes and lets make, shrunk to the league) and the POOL OF
// SCENARIOS, one per game and side of the season. A scenario keeps, taken together as the game gave them, what each side did compared with what it was expected to do (the four factors), how
// fast the game went compared with what the two teams usually play, and how the margin went compared with what the ratings said. Whole games are kept because the factors and the margin of a
// game are not independent: that is what lets the preview say «when they rebound this much, we win this often» without inventing a correlation.
// Expectations use the levels of the whole season (in-sample): the residuals are a little narrower than they will be, which the preview makes up with a kernel (`scenarios.ts`).
import { buildRatings, matchupPace, type GameResult } from './gameLog'
import { boxOf, FACTOR_KEYS, factors, leagueFactors, shrunkLevel, sumBoxes, type Box, type Factors, type TeamLevel } from './factors'
import { DEFAULT_PACE, type TeamRatings } from './teamRatings'
import { wpParams } from './winProb'

export interface Scenario {
  /** What the own side did minus what it was expected to do, per factor. */
  dOwn: Factors
  /** The same for the rival side. */
  dRiv: Factors
  /** The pace of the game over the usual pace of its two teams. */
  rho: number
  /** The margin of the game over what the ratings and the home court said, per square root of its possessions. */
  z: number
}

export interface TeamSums { for: Box; against: Box; games: number }

export interface ForecastModel {
  games: GameResult[]
  ratings: TeamRatings
  gender?: string
  /** The factors of the league (every side of every game with rows). */
  league: Factors
  sums: Map<string, TeamSums>
  /** The level of a team shrunk to the league; the league itself for a team with no rows. */
  level: (team: string) => TeamLevel
  pool: Scenario[]
}

const clamp01 = (x: number): number => Math.min(1, Math.max(0, x))

/** What `attack` is expected to make against `defender`: what it usually makes plus what the other usually lets, against the league. */
export function expectedFactors(attack: TeamLevel, defender: TeamLevel, league: Factors): Factors {
  return Object.fromEntries(FACTOR_KEYS.map(k => [k, clamp01(attack.attack[k] + defender.defence[k] - league[k])])) as Factors
}

function sumsOf(games: GameResult[]): Map<string, TeamSums> {
  const per = new Map<string, { own: Box[]; opp: Box[] }>()
  for (const g of games) {
    if (!g.homeRow || !g.awayRow) continue
    for (const [team, row] of [[g.home, g.homeRow], [g.away, g.awayRow]] as const) {
      const entry = per.get(team) ?? { own: [], opp: [] }
      entry.own.push(boxOf(row, 'own'))
      entry.opp.push(boxOf(row, 'opp'))
      per.set(team, entry)
    }
  }
  return new Map([...per].map(([team, e]) => [team, { for: sumBoxes(e.own), against: sumBoxes(e.opp), games: e.own.length }]))
}

function scenariosOf(games: GameResult[], ratings: TeamRatings, level: (team: string) => TeamLevel, league: Factors, gender?: string): Scenario[] {
  const { homeAdv } = wpParams(gender)
  const paces = new Map<string, number>()
  const usual = (a: string, b: string): number => {
    const key = a < b ? `${a}|${b}` : `${b}|${a}`
    if (!paces.has(key)) paces.set(key, matchupPace(games, a, b))
    return paces.get(key)!
  }
  const out: Scenario[] = []
  for (const g of games) {
    if (!g.homeRow || !g.awayRow) continue
    const sides = [[g.home, g.away, g.homeRow, g.awayRow, 1], [g.away, g.home, g.awayRow, g.homeRow, -1]] as const
    for (const [o, r, rowO, rowR, court] of sides) {
      const [boxO, boxR] = [boxOf(rowO, 'own'), boxOf(rowR, 'own')]
      const [eo, er] = [expectedFactors(level(o), level(r), league), expectedFactors(level(r), level(o), league)]
      const [fo, fr] = [factors(boxO, boxR), factors(boxR, boxO)]
      const pbar = usual(o, r)
      const pace = g.pace ?? (pbar || DEFAULT_PACE)
      const expectedMargin = ratings.rating(o) - ratings.rating(r) + (court * homeAdv * (pbar || DEFAULT_PACE)) / 100
      out.push({
        dOwn: Object.fromEntries(FACTOR_KEYS.map(k => [k, fo[k] - eo[k]])) as Factors,
        dRiv: Object.fromEntries(FACTOR_KEYS.map(k => [k, fr[k] - er[k]])) as Factors,
        rho: g.pace && pbar > 0 ? g.pace / pbar : 1,
        z: (court * g.margin - expectedMargin) / Math.sqrt(pace),
      })
    }
  }
  return out
}

/** The model of a competition from its games (`gameLog.buildGames`); `gender` picks the calibrated spread and home court. */
export function buildModel(games: GameResult[], gender?: string): ForecastModel {
  const ratings = buildRatings(games)
  const sums = sumsOf(games)
  const league = leagueFactors([...sums.values()].map(s => s.for))
  const cache = new Map<string, TeamLevel>()
  const level = (team: string): TeamLevel => {
    const key = String(team)
    if (!cache.has(key)) {
      const s = sums.get(key)
      cache.set(key, s ? shrunkLevel({ for: s.for, against: s.against }, league, s.games) : { attack: league, defence: league })
    }
    return cache.get(key)!
  }
  return { games, ratings, gender, league, sums, level, pool: scenariosOf(games, ratings, level, league, gender) }
}
