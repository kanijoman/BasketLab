// The variables of a match the projection can be asked about (#936): the possessions of the game and, for each side, its points, its points per 100 possessions (OER) and its four factors.
// A question is one or more conditions on them («our points: more than 70», «their eFG: less than 40 %»), all of which must hold.
import { FACTOR_KEYS, boxOf, factors, type FactorKey } from '../factors'
import { gamePossessions, type GameResult } from '../gameLog'

export type Side = 'own' | 'rival'
export type SideMeasure = 'points' | 'oer' | FactorKey
export type VariableId = 'game.possessions' | `${Side}.${SideMeasure}`

export interface Variable {
  id: VariableId
  /** Whose it is (none for the possessions, which are the game's). */
  side: Side | null
  measure: 'possessions' | SideMeasure
  /**
   * How a scenario says it: the possessions and the factors are what the scenario is (it is in or out of a condition); the points, and the points per 100 possessions, are normal around the
   * scenario (the kernel), so a condition on them is an interval of the points of that side.
   */
  kind: 'scenario' | 'points'
  /**
   * Whether the walk-forward evaluation backs a probability of winning in the games where it happens (#938). The rule of #857: without support, information only (how often, what those
   * games look like and the season's record) and no figure. The possessions start without it (the evaluation of 11/11/2026 found none for the pace).
   */
  supported: boolean
}

const SIDE_MEASURES: SideMeasure[] = ['points', 'oer', ...FACTOR_KEYS]

export const VARIABLES: Variable[] = [
  { id: 'game.possessions', side: null, measure: 'possessions', kind: 'scenario', supported: false },
  ...(['own', 'rival'] as const).flatMap(side => SIDE_MEASURES.map((measure): Variable => ({
    id: `${side}.${measure}`, side, measure, kind: measure === 'points' || measure === 'oer' ? 'points' : 'scenario', supported: true,
  }))),
]

const BY_ID = new Map(VARIABLES.map(v => [v.id, v]))
export const variableOf = (id: VariableId): Variable => BY_ID.get(id)!

/** «more than» (`gt`) or «less than» (`lt`) a value, strictly: «más de 70 puntos» is 71 or more. Factors are ratios (0.4 = 40 %). */
export interface Condition { variable: VariableId; op: 'lt' | 'gt'; value: number }

export const meets = (value: number, c: Condition): boolean => (c.op === 'gt' ? value > c.value : value < c.value)

/** What a game that was played says of a variable from the side of `team` (`own` is `team`); null when the game has no box score or `team` did not play it. */
export function gameValue(g: GameResult, team: string, id: VariableId): number | null {
  const row = g.home === team ? g.homeRow : g.away === team ? g.awayRow : undefined
  if (!row) return null
  const v = variableOf(id)
  if (v.measure === 'possessions') return g.pace
  const [own, opp] = [boxOf(row, 'own'), boxOf(row, 'opp')]
  const [mine, theirs] = v.side === 'own' ? [own, opp] : [opp, own]
  if (v.measure === 'points') return mine.pts
  if (v.measure === 'oer') return (100 * mine.pts) / gamePossessions(g, row)
  return factors(mine, theirs)[v.measure]
}
