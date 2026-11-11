// The preview of a match (#847): the composition of the models for ONE own team against ONE rival where it is played. The headline (the win probability of the live engine's model) is always there;
// the scenarios, the objectives and the matchup need games to compare with, and without enough of them the page shows the headline alone.
import { gamesOf, matchupPace } from './gameLog'
import { leversOf, type Levers } from './levers'
import { matchupRows, type MatchupRow } from './matchup'
import type { ForecastModel } from './pool'
import { bucketsOf, density, evaluate, type Bucket } from './scenarios'
import { headline, type Court, type Headline } from './winProb'

/** Below this many games a team is too little known for the preview to be trusted. */
export const MIN_GAMES = 5
/** Below this many scenarios there is nothing to compare with. */
export const MIN_POOL = 30

export type Reason = { kind: 'few-games'; team: string; name: string; games: number } | { kind: 'small-pool'; size: number }

export interface Confidence { level: 'baja' | 'normal'; reasons: Reason[] }

export interface PreviewDetail {
  scenarios: Bucket[]
  density: { margin: number; p: number }[]
  levers: Levers
  matchup: MatchupRow[]
  poolSize: number
  /** The spread of the scenarios and of the kernel (points), and the expected margin that anchors them to the headline (see `scenarios.evaluate`). */
  residualSd: number
  sigmaU: number
  muStar: number
  anchored: boolean
}

export interface MatchPreview {
  own: string
  rival: string
  court: Court
  headline: Headline
  confidence: Confidence
  /** `null` when there are too few scenarios to compare with. */
  detail: PreviewDetail | null
}

function nameOf(model: ForecastModel, team: string): string {
  const game = model.games.find(g => g.home === team || g.away === team)
  return game ? (game.home === team ? game.homeName : game.awayName) : team
}

function confidenceOf(model: ForecastModel, own: string, rival: string): Confidence {
  const reasons: Reason[] = [own, rival]
    .map((team): Reason => ({ kind: 'few-games', team, name: nameOf(model, team), games: gamesOf(model.games, team).length }))
    .filter(r => r.kind === 'few-games' && r.games < MIN_GAMES)
  if (model.pool.length < MIN_POOL) reasons.push({ kind: 'small-pool', size: model.pool.length })
  return { level: reasons.length ? 'baja' : 'normal', reasons }
}

export function buildPreview(model: ForecastModel, own: string, rival: string, court: Court): MatchPreview {
  const confidence = confidenceOf(model, own, rival)
  const head = headline({ ratings: model.ratings, own, rival, court, pace: matchupPace(model.games, own, rival), gender: model.gender })
  const ev = model.pool.length >= MIN_POOL ? evaluate(model, own, rival, court) : null
  const detail: PreviewDetail | null = ev && {
    scenarios: bucketsOf(ev), density: density(ev), levers: leversOf(model, ev), matchup: matchupRows(model, own, rival), poolSize: model.pool.length,
    residualSd: ev.residualSd, sigmaU: ev.sigmaU, muStar: ev.muStar, anchored: ev.anchored,
  }
  return { own, rival, court, headline: head, confidence, detail }
}
