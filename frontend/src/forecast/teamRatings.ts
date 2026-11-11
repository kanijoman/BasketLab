// The Bayesian (Kalman) rating of the teams of a competition (#846): a port of `live_prep.team_rating.TeamRatings`, the prior of the matchup that the win probability lives on (#567).
// Every team has a rating in points per game and a variance (how sure we are of it). A result moves the two teams by the part of the surprise (the margin minus the expected one: rating gap plus
// home court) that matches how unsure each one was; after each game every variance grows a little, so the rating follows a team that changes during the season. The home court is learnt from
// the margins. Parity with Python is pinned by `tests/local_vectors/forecast.json`: change `team_rating.py` and the vectors (and this file) must follow.

export const P0 = 60            // variance (points per game squared) of a team never seen: about +-8 points
export const Q_GAME = 0.3       // variance added to a team after each of its games: the season moves
export const NOISE = 144        // variance of the margin of one game around its expectation (12 points)
export const HOME_PRIOR = 3     // home court (points) before any result is known
export const HOME_WEIGHT = 20   // the home court prior counts as this many games
export const DEFAULT_PACE = 70  // possessions per 40 minutes when the pace of the matchup is not known

export class TeamRatings {
  private readonly mean = new Map<string, number>()
  private readonly vari = new Map<string, number>()
  private homeSum = HOME_PRIOR * HOME_WEIGHT
  private homeN = HOME_WEIGHT

  /** Points per game above the average team of the competition (0 for a team never seen). Ids are compared as texts: FBCYL has numbers. */
  rating(team: string): number {
    return this.mean.get(String(team)) ?? 0
  }

  /** How unsure the rating is, in points per game squared (`P0` for a team never seen). */
  variance(team: string): number {
    return this.vari.get(String(team)) ?? P0
  }

  homeAdvantage(): number {
    return this.homeSum / this.homeN
  }

  /** One result: `margin` = points of the home team minus points of the away team. */
  update(home: string, away: string, margin: number): void {
    const h = String(home)
    const a = String(away)
    for (const team of [h, a]) {
      if (!this.mean.has(team)) this.mean.set(team, 0)
      if (!this.vari.has(team)) this.vari.set(team, P0)
    }
    const [mh, ma, vh, va] = [this.mean.get(h)!, this.mean.get(a)!, this.vari.get(h)!, this.vari.get(a)!]
    const surprise = margin - (mh - ma + this.homeAdvantage())
    const spread = vh + va + NOISE
    const gainHome = vh / spread
    const gainAway = va / spread
    this.mean.set(h, mh + gainHome * surprise)
    this.mean.set(a, ma - gainAway * surprise)
    this.vari.set(h, vh * (1 - gainHome) + Q_GAME)
    this.vari.set(a, va * (1 - gainAway) + Q_GAME)
    this.homeSum += margin
    this.homeN += 1
  }

  /** Expected margin of `own` against `rival` on a neutral court, per 100 possessions (the unit of `net_rtg_prior`); a pace that is not positive is the default one. */
  gapPer100(own: string, rival: string, pace: number): number {
    return ((this.rating(own) - this.rating(rival)) * 100) / (pace > 0 ? pace : DEFAULT_PACE)
  }
}
