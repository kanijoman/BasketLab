/**
 * The registry of the team formulas (#1153): `config/formulas.json` defines every rate once (Python's `src/stats/formulas.py` and the Mongo pipelines read the same file). Each formula is
 * `scale * (num) / (den)`, num and den linear combinations of counters; `net_rating` is a difference. A rate with an empty denominator is `null` (the tables show 0 or «-» as they always did).
 */
import registry from '@config/formulas.json'

export type Counters = Record<(typeof registry.counters)[number], number>
type Terms = Record<string, number>
interface Formula { num?: Terms; den?: Terms; scale?: number; minus?: [string, string] }

export const COUNTERS: string[] = registry.counters
export const FORMULAS = registry.formulas as unknown as Record<string, Formula>

function combo(terms: Terms, counters: Counters): number {
  let total = 0
  for (const [name, coefficient] of Object.entries(terms)) {
    const value = (counters as Record<string, number>)[name]
    if (value === undefined) throw new Error(`formula counter «${name}» is missing`)            // never a silent zero
    total += coefficient * value
  }
  return total
}

/** The value of the formula `name` for `counters`, or `null` when a denominator is 0 (Python's `evaluate`, term by term in the same order). */
export function evaluate(name: string, counters: Counters): number | null {
  const formula = FORMULAS[name]
  if (formula.minus) {
    const [left, right] = formula.minus.map(part => evaluate(part, counters))
    return left === null || right === null ? null : left - right
  }
  const denominator = combo(formula.den as Terms, counters)
  if (denominator === 0) return null
  return (combo(formula.num as Terms, counters) / denominator) * (formula.scale as number)
}

export function evaluateAll(counters: Counters): Record<string, number | null> {
  return Object.fromEntries(Object.keys(FORMULAS).map(name => [name, evaluate(name, counters)]))
}
