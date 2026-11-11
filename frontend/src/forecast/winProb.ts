// The win probability at tip-off (#846): `live_core.win_prob.WinProbabilityModel.evaluate` with nothing played. The final margin is Normal(mu * possessions / 100, sigma^2) where `mu` is the matchup
// prior of the package (the rating gap per 100 possessions, rounded to 3 decimals as `package_builder` does) plus the home court, and P(win) = Phi(mean / sigma). Sigma and the home court are
// calibrated per family of competitions (`WP_BY_GENDER`, study of 26/10/2026 on 2,886 games); a competition that does not say its family has the neutral defaults of `RuleConfig`.
import { pyRound } from '@/localdata/pyMath'
import { phi } from './normal'
import { DEFAULT_PACE, type TeamRatings } from './teamRatings'

export interface WpParams { sigma: number; homeAdv: number }

/** `WP_BY_GENDER` of `live_core/config.py` and the defaults of `RuleConfig` (`wp_sigma` 12, `wp_home_adv` 4). The parity vectors fail if they drift. */
const BY_GENDER: Record<string, WpParams> = { F: { sigma: 14, homeAdv: 5 }, M: { sigma: 15, homeAdv: 7 } }
const NEUTRAL_PARAMS: WpParams = { sigma: 12, homeAdv: 4 }

export const wpParams = (gender?: string): WpParams => (gender ? BY_GENDER[gender] : undefined) ?? NEUTRAL_PARAMS

/** The z of the central 80 % of a normal distribution (the usual range of a margin). */
export const Z80 = 1.2815515655446004

/** Who plays at home: the own team, the rival, or nobody. */
export type Court = 'own' | 'rival' | 'neutral'

export interface Headline {
  /** The expected net rating of the matchup per 100 possessions, without the home court (rounded to 3 decimals: what the package carries). */
  gap100: number
  /** The expected margin of the own team, in points. */
  mu: number
  /** The spread of the margin of a game, in points. */
  sigma: number
  /** The possessions of the game the expectation is made at. */
  pace: number
  /** The probability that the own team wins. */
  p: number
  /** The central 80 % of the margin. */
  range80: [number, number]
}

export interface HeadlineInput {
  ratings: TeamRatings
  own: string
  rival: string
  court: Court
  /** Possessions per 40 minutes of the matchup (the mean of the paces of both teams); 0 when it is not known. */
  pace: number
  gender?: string
}

export function headline({ ratings, own, rival, court, pace, gender }: HeadlineInput): Headline {
  const { sigma, homeAdv } = wpParams(gender)
  const gap100 = pyRound(ratings.gapPer100(own, rival, pace), 3)
  const possessions = pace > 0 ? pace : DEFAULT_PACE
  const venue = court === 'own' ? 1 : court === 'rival' ? -1 : 0
  const mu = ((gap100 + venue * homeAdv) * possessions) / 100
  return { gap100, mu, sigma, pace: possessions, p: phi(mu / sigma), range80: [mu - Z80 * sigma, mu + Z80 * sigma] }
}
