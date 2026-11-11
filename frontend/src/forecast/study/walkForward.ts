// The walk-forward evaluation of the forecast (#851). Every forecast is made with the games BEFORE the one it is judged on and nothing else, so what is measured is what the pages would have said
// that day. Three pieces: the headline game by game (what `winProb` says), the preview (scenarios and objectives, `buildPreview` on the games so far) and the simulation of the league (cut
// after cut of a season, judged against the final table). Pure functions over `GameResult[]`; the runner (`backtest.study.ts`) reads the competitions and writes the report.
import type { Calendar } from '@/webdata/calendar'
import { pyRound } from '@/localdata/pyMath'
import { boxOf, factors } from '../factors'
import type { GameResult } from '../gameLog'
import { bestPaceLever, paceCandidates, type Lever } from '../levers'
import { buildModel } from '../pool'
import { evaluate } from '../scenarios'
import { buildPreview } from '../preview'
import { pTop, simulateSeason } from '../seasonSim'
import { standingsOf } from '../standings'
import { TeamRatings } from '../teamRatings'
import { headline } from '../winProb'
import { multiclassBrier, rps } from './metrics'

const outcome = (g: GameResult): number => (g.tied ? 0.5 : g.margin > 0 ? 1 : 0)

/** The pace of a matchup from the games played so far, kept incrementally (the same figure as `gameLog.matchupPace`: the mean of the paces of the games of both teams, to one decimal). */
class PaceBook {
  private readonly sums = new Map<string, [number, number]>()

  add(g: GameResult): void {
    if (g.pace === null) return
    for (const team of [g.home, g.away]) {
      const [sum, n] = this.sums.get(team) ?? [0, 0]
      this.sums.set(team, [sum + g.pace, n + 1])
    }
  }

  pace(a: string, b: string): number {
    const [sa, na] = this.sums.get(a) ?? [0, 0]
    const [sb, nb] = this.sums.get(b) ?? [0, 0]
    return na + nb ? pyRound((sa + sb) / (na + nb), 1) : 0
  }
}

export interface HeadlineRow {
  /** The index of the game. */
  k: number
  /** The games the less known of the two teams had played before it. */
  played: number
  /** The forecast of the home team winning, what happened (1, 0, or 0.5 for a tie) and the baseline: the home team wins as often as it has so far. */
  p: number
  y: number
  baseline: number
}

/** The headline of every game with the ratings and paces of the games before it. */
export function walkForwardHeadline(games: GameResult[], gender?: string): HeadlineRow[] {
  const ratings = new TeamRatings()
  const paces = new PaceBook()
  const played = new Map<string, number>()
  let homeWins = 0
  return games.map((g, k): HeadlineRow => {
    const h = headline({ ratings, own: g.home, rival: g.away, court: 'own', pace: paces.pace(g.home, g.away), gender })
    const row = { k, played: Math.min(played.get(g.home) ?? 0, played.get(g.away) ?? 0), p: h.p, y: outcome(g), baseline: (homeWins + 1) / (k + 2) }
    ratings.update(g.home, g.away, g.margin)
    paces.add(g)
    for (const team of [g.home, g.away]) played.set(team, (played.get(team) ?? 0) + 1)
    homeWins += g.margin > 0 ? 1 : 0
    return row
  })
}

export interface LeverRecord {
  k: number
  side: Lever['side']
  /** What the objective said: the probability of winning when it is reached, and the headline it is compared with. */
  pWin: number
  headline: number
  /** Whether the game reached the target, and what happened for the team whose objective it was. */
  met: boolean
  y: number
}

export interface PreviewSample { k: number; headline: number; anchored: boolean; muShift: number; residualSd: number; sigmaU: number }

export interface PreviewStudy {
  samples: PreviewSample[]
  /** Games that could not be previewed (too few games to compare with). */
  skipped: number
  anchoredFailures: number
  buckets: { n: number; brier: number; brierBaseline: number; logScore: number; logScoreBaseline: number }
  levers: LeverRecord[]
}

/** 0 a big loss, 1 a close one, 2 a close win, 3 a big one (the margin of the own team; a tie has none). */
const bucketOf = (margin: number): number => (margin < -10.5 ? 0 : margin < 0 ? 1 : margin <= 10.5 ? 2 : 3)

/** How often each kind of game had happened in `games` (both sides of each), with one game of each kind as the starting point. */
function bucketShares(games: GameResult[]): number[] {
  const counts = [1, 1, 1, 1]
  for (const g of games) if (!g.tied) { counts[bucketOf(g.margin)]++; counts[bucketOf(-g.margin)]++ }
  const total = counts.reduce((a, b) => a + b, 0)
  return counts.map(c => c / total)
}

function leverRecords(k: number, g: GameResult, own: string, levers: Lever[], headlineP: number, y: number): LeverRecord[] {
  const row = g.home === own ? g.homeRow : g.awayRow
  if (!row) return []
  return levers.map(l => {
    const [o, r] = [boxOf(row, 'own'), boxOf(row, 'opp')]
    const value = l.side === 'pace' ? (g.pace ?? NaN) : l.side === 'attack' ? factors(o, r)[l.factor!] : factors(r, o)[l.factor!]
    return { k, side: l.side, pWin: l.pWin, headline: headlineP, met: l.direction === 'up' ? value >= l.threshold : value <= l.threshold, y }
  })
}

/** The preview of the games from `from` on, every `every` games, each with the model of the games before it, judged against the game. */
export function walkForwardPreviews(games: GameResult[], gender: string | undefined, { from = 40, every = 4 }: { from?: number; every?: number } = {}): PreviewStudy {
  const study: PreviewStudy = { samples: [], skipped: 0, anchoredFailures: 0, buckets: { n: 0, brier: 0, brierBaseline: 0, logScore: 0, logScoreBaseline: 0 }, levers: [] }
  for (let k = from; k < games.length; k += every) {
    const g = games[k]
    const model = buildModel(games.slice(0, k), gender)
    const shares = bucketShares(games.slice(0, k))
    for (const [own, rival, court, margin] of [[g.home, g.away, 'own', g.margin], [g.away, g.home, 'rival', -g.margin]] as const) {
      const preview = buildPreview(model, own, rival, court)
      if (!preview.detail) { if (court === 'own') study.skipped++; continue }
      const { detail } = preview
      const y = g.tied ? 0.5 : margin > 0 ? 1 : 0
      if (court === 'own') {
        if (!detail.anchored) study.anchoredFailures++
        study.samples.push({ k, headline: preview.headline.p, anchored: detail.anchored, muShift: detail.muStar - preview.headline.mu, residualSd: detail.residualSd, sigmaU: detail.sigmaU })
        if (!g.tied) {
          const probs = detail.scenarios.map(b => b.p)
          const actual = bucketOf(margin)
          study.buckets.n++
          study.buckets.brier += multiclassBrier(probs, actual)
          study.buckets.brierBaseline += multiclassBrier(shares, actual)
          study.buckets.logScore += -Math.log(probs[actual])
          study.buckets.logScoreBaseline += -Math.log(shares[actual])
        }
      }
      const { attack, defence } = detail.levers
      const ev = evaluate(model, own, rival, court)                                 // the pace is not an objective of the page any more (#857) but the study still measures it
      const pace = ev ? bestPaceLever(paceCandidates(model, ev)) : null
      study.levers.push(...leverRecords(k, g, own, [...attack, ...defence, ...(pace ? [pace] : [])], preview.headline.p, y))
    }
  }
  const n = study.buckets.n
  for (const key of ['brier', 'brierBaseline', 'logScore', 'logScoreBaseline'] as const) study.buckets[key] = n ? study.buckets[key] / n : NaN
  return study
}

export interface SeasonRow {
  cut: number
  /** The games played before the cut. */
  played: number
  teams: number
  /** Ranked probability score of the final position, Brier of being first and of being in the first four: the simulation, and the baseline of the order of the table on the day of the cut. */
  rps: number
  rpsBaseline: number
  brierFirst: number
  brierFirstBaseline: number
  brierTop4: number
  brierTop4Baseline: number
  /** What the simulation cost, in milliseconds. */
  ms: number
}

function calendarOf(results: GameResult[], pending: GameResult[]): Calendar {
  const match = (g: GameResult, kind: 'result' | 'scheduled', i: number) => ({
    code: g.id, match_id: g.id, round: i + 1, kind, start: null, home: { id: g.home, name: g.homeName }, away: { id: g.away, name: g.awayName },
    score: kind === 'result' ? ([g.homePoints, g.awayPoints] as [number, number]) : null,
  })
  return { format: 1, collection: 'study', league: 'feb', games: results.length + pending.length, ties_allowed: false, matches: [...results.map((g, i) => match(g, 'result', i)), ...pending.map((g, i) => match(g, 'scheduled', results.length + i))] }
}

/** The simulation of the league after each fraction of the season, with the games of the rest of the season as the calendar, judged against the table at the end. */
export function walkForwardSeason(games: GameResult[], gender: string | undefined, { cuts = [0.25, 0.5, 0.75], simulations = 2000 }: { cuts?: number[]; simulations?: number } = {}): SeasonRow[] {
  const final = new Map(standingsOf(games).map(r => [r.team, r.position]))
  return cuts.map((cut): SeasonRow => {
    const played = Math.floor(games.length * cut)
    const results = games.slice(0, played)
    const model = buildModel(results, gender)
    const started = performance.now()
    const sim = simulateSeason(model, calendarOf(results, games.slice(played)), { n: simulations, seed: `study-${cut}` })
    const ms = performance.now() - started
    const today = new Map(sim.table.map(r => [r.team, r.position]))
    const scores = { rps: 0, rpsBaseline: 0, first: 0, firstBase: 0, top4: 0, top4Base: 0 }
    sim.teams.forEach((team, t) => {
      const actual = final.get(team)! - 1
      const now = today.get(team)! - 1
      const probs = Array.from(sim.positionCounts[t], c => c / sim.n)
      scores.rps += rps(probs, actual)
      scores.rpsBaseline += rps(probs.map((_, i) => (i === now ? 1 : 0)), actual)
      scores.first += (sim.pFirst[t] - (actual === 0 ? 1 : 0)) ** 2
      scores.firstBase += ((now === 0 ? 1 : 0) - (actual === 0 ? 1 : 0)) ** 2
      scores.top4 += (pTop(sim, t, 4) - (actual < 4 ? 1 : 0)) ** 2
      scores.top4Base += ((now < 4 ? 1 : 0) - (actual < 4 ? 1 : 0)) ** 2
    })
    const T = sim.teams.length
    return {
      cut, played, teams: T, ms, rps: scores.rps / T, rpsBaseline: scores.rpsBaseline / T, brierFirst: scores.first / T, brierFirstBaseline: scores.firstBase / T,
      brierTop4: scores.top4 / T, brierTop4Baseline: scores.top4Base / T,
    }
  })
}
