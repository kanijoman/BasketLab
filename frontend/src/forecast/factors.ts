// The four factors of the live engine (#846): `live_core.four_factors` (Oliver: eFG 40, TOV 25, ORB 20, FT 15) and the level of a team shrunk to the league
// (`live_prep.package_builder.shrunk_team_level`), computed from the rows of a competition instead of from a play-by-play. Conventions of the project: TOV% = TOV / (FGA + 0.44 FTA + TOV)
// (not turnovers per possession, as the season tables use), FTr = FTA / FGA, ORB% = ORB / (ORB + rival DRB). Parity with Python is pinned by `tests/local_vectors/forecast.json`.
import { pyRound } from '@/localdata/pyMath'
import type { GameRow } from '@/localdata/aggregateTeams'

export const FACTOR_KEYS = ['efg', 'tov', 'orb', 'ftr'] as const
export type FactorKey = (typeof FACTOR_KEYS)[number]
export type Factors = Record<FactorKey, number>

export const WEIGHTS: Factors = { efg: 0.4, tov: 0.25, orb: 0.2, ftr: 0.15 }
export const FT_POSSESSION_COST = 0.44
/** The prior weight of the league in the level of a team: games / (games + 6). */
export const SHRINK_GAMES = 6

/** The stat totals of one side of a game, with the keys the live engine uses. */
export interface Box { fg2m: number; fg2a: number; fg3m: number; fg3a: number; ftm: number; fta: number; orb: number; drb: number; tov: number; pts: number }

const KEYS: (keyof Box)[] = ['fg2m', 'fg2a', 'fg3m', 'fg3a', 'ftm', 'fta', 'orb', 'drb', 'tov', 'pts']

/** The fields of a game row of each stat, own side and opponent side (the same table as the parity vectors: `forecast_vectors.OWN_STATS` / `OPP_STATS`). */
const FIELDS: Record<'own' | 'opp', Record<keyof Box, keyof GameRow>> = {
  own: { fg2m: 'fg2_made', fg2a: 'fg2_attempts', fg3m: 'fg3_made', fg3a: 'fg3_attempts', ftm: 'ft_made', fta: 'ft_attempts', orb: 'off_rebounds', drb: 'def_rebounds', tov: 'turnovers', pts: 'points' },
  opp: { fg2m: 'opponent_fg2_made', fg2a: 'opponent_fg2_attempts', fg3m: 'opponent_fg3_made', fg3a: 'opponent_fg3_attempts', ftm: 'opponent_ft_made', fta: 'opponent_ft_attempts',
         orb: 'opponent_off_rebounds', drb: 'opponent_def_rebounds', tov: 'opponent_turnovers', pts: 'opponent_points' },
}

/** The stats of one side of a game row. */
export function boxOf(row: GameRow, side: 'own' | 'opp'): Box {
  const out = {} as Box
  for (const key of KEYS) out[key] = Number(row[FIELDS[side][key]] ?? 0)
  return out
}

export function sumBoxes(boxes: Box[]): Box {
  const out = Object.fromEntries(KEYS.map(k => [k, 0])) as unknown as Box
  for (const b of boxes) for (const k of KEYS) out[k] += b[k]
  return out
}

const ratio = (num: number, den: number): number => (den ? num / den : 0)
const fga = (s: Box): number => s.fg2a + s.fg3a
const fgm = (s: Box): number => s.fg2m + s.fg3m

/** Possessions of a side: FGA - ORB + TOV + 0.44 FTA. */
export const possessions = (s: Box): number => fga(s) - s.orb + s.tov + FT_POSSESSION_COST * s.fta

/** The offensive four factors of `own` (the rival's defensive rebounds feed ORB%). */
export function factors(own: Box, opp: Box): Factors {
  return {
    efg: ratio(fgm(own) + 0.5 * own.fg3m, fga(own)),
    tov: ratio(own.tov, fga(own) + FT_POSSESSION_COST * own.fta + own.tov),
    orb: ratio(own.orb, own.orb + opp.drb),
    ftr: ratio(own.fta, fga(own)),
  }
}

// fallbacks when too few possessions to estimate the rates from the side itself
const FGA_PER_POSS = 0.88
const PPP = 1.0
const MISS_PER_POSS = 0.5
const FT_PCT = 0.72
const MIN_POSS_FOR_RATES = 10

/** Points per 100 possessions per 1.0 of each factor differential (the analytic marginals of the engine). */
export function pointsPerUnit(own: Box): Factors {
  const poss = possessions(own)
  const reliable = poss >= MIN_POSS_FOR_RATES
  const fgaRate = reliable ? fga(own) / poss : FGA_PER_POSS
  const ppp = reliable && own.pts ? own.pts / poss : PPP
  const missRate = reliable ? (fga(own) - fgm(own)) / poss : MISS_PER_POSS
  const ftPct = own.fta >= 5 ? own.ftm / own.fta : FT_PCT
  return { efg: 2 * fgaRate * 100, tov: ppp * 100, orb: missRate * ppp * 100, ftr: fgaRate * ftPct * 100 }
}

/** The factors of the league: its sides' totals against themselves, as the package does with `league_sums`. */
export const leagueFactors = (boxes: Box[]): Factors => {
  const total = sumBoxes(boxes)
  return factors(total, total)
}

export interface TeamLevel { attack: Factors; defence: Factors }

/** The level of a team over its `games`: what it makes (attack) and lets its opponents make (defence), each shrunk towards the `league` by games / (games + 6), rounded to 4 decimals as the package. */
export function shrunkLevel(sums: { for: Box; against: Box }, league: Factors, games: number): TeamLevel {
  const weight = games / (games + SHRINK_GAMES)
  const shrink = (level: Factors): Factors =>
    Object.fromEntries(FACTOR_KEYS.map(k => [k, pyRound(league[k] + (level[k] - league[k]) * weight, 4)])) as Factors
  return { attack: shrink(factors(sums.for, sums.against)), defence: shrink(factors(sums.against, sums.for)) }
}
