// How each team responds to the pace (#937). The pool mixes the games of every team, so in the projection the way the factors and the points per 100 possessions move with the pace of a game is
// the league's. Here every team has its own slope: the regression of its residuals (what it made, attack, and what it let make, defence, against what was expected) on the pace of its games
// over their usual pace (`rho − 1`), shrunk towards the league's by games / (games + k) like the levels of the factors. Played by two teams, a scenario moves by what their slopes say beyond the
// league's at that scenario's pace: what we make, by our attack and their defence; what they make, by their attack and our defence (`expectedFactors` adds them up the same way).
// With one season of a league a slope is noisy: the walk-forward evaluation (#938) decides whether the layer goes to the page and with which k.
import { FACTOR_KEYS, type FactorKey } from '../factors'
import type { ForecastModel, Scenario } from '../pool'

export type ResponseKey = FactorKey | 'oer'
export const RESPONSE_KEYS: ResponseKey[] = [...FACTOR_KEYS, 'oer']
export type Slopes = Record<ResponseKey, number>

/** What a team makes (attack) and lets make (defence) per unit of `rho − 1`. */
export interface TeamSlopes { attack: Slopes; defence: Slopes }

export interface PaceResponse {
  /** The slope of every side of the league (attack and defence are the same: both sides of every game are in the pool). */
  league: Slopes
  /** The slopes of a team from its own games alone; the league's for a team with no games. */
  raw: (team: string) => TeamSlopes
  /** The slopes used: the team's shrunk towards the league's. */
  level: (team: string) => TeamSlopes
}

/** The games a team needs for its slope to be halfway between its own and the league's, until the evaluation chooses (#938). */
export const PACE_SHRINK_GAMES = 20

const value = (s: Scenario, key: ResponseKey, side: 'own' | 'rival'): number =>
  key === 'oer' ? (side === 'own' ? s.oOwn : s.oRiv) : (side === 'own' ? s.dOwn : s.dRiv)[key]

/** The least-squares slope (with intercept) of a residual on `rho − 1` over some scenarios; 0 when their pace does not vary. */
function slopes(scenarios: Scenario[], side: 'own' | 'rival'): Slopes {
  const xs = scenarios.map(s => s.rho - 1)
  const mx = xs.reduce((a, b) => a + b, 0) / (xs.length || 1)
  const sxx = xs.reduce((acc, x) => acc + (x - mx) ** 2, 0)
  return Object.fromEntries(RESPONSE_KEYS.map(key => {
    const ys = scenarios.map(s => value(s, key, side))
    const my = ys.reduce((a, b) => a + b, 0) / (ys.length || 1)
    return [key, sxx > 0 ? xs.reduce((acc, x, i) => acc + (x - mx) * (ys[i] - my), 0) / sxx : 0]
  })) as Slopes
}

/** How the teams of a competition respond to the pace, with `k` games of shrinkage towards the league. */
export function paceResponse(model: ForecastModel, k = PACE_SHRINK_GAMES): PaceResponse {
  const league = slopes(model.pool, 'own')
  const byTeam = new Map<string, Scenario[]>()
  for (const s of model.pool) byTeam.set(s.own, [...(byTeam.get(s.own) ?? []), s])
  const raws = new Map([...byTeam].map(([team, list]) => [team, { attack: slopes(list, 'own'), defence: slopes(list, 'rival') }]))
  const raw = (team: string): TeamSlopes => raws.get(String(team)) ?? { attack: league, defence: league }
  const level = (team: string): TeamSlopes => {
    const n = byTeam.get(String(team))?.length ?? 0
    const weight = n / (n + k)
    const shrink = (own: Slopes): Slopes => Object.fromEntries(RESPONSE_KEYS.map(key => [key, league[key] + (own[key] - league[key]) * weight])) as Slopes
    const r = raw(team)
    return { attack: shrink(r.attack), defence: shrink(r.defence) }
  }
  return { league, raw, level }
}

/** What a side of a matchup makes beyond the league per unit of `rho − 1`: its attack plus the other's defence, each beyond the league. */
export const extraSlope = (r: PaceResponse, attack: string, defender: string, key: ResponseKey): number =>
  r.level(attack).attack[key] - r.league[key] + r.level(defender).defence[key] - r.league[key]
