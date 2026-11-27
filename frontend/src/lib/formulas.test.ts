import { describe, expect, it } from 'vitest'
import { COUNTERS, FORMULAS, evaluate, evaluateAll, type Counters } from './formulas'
import vector from '../../../tests/formulas/vector.json'

// The registry of the team formulas (#1153): `config/formulas.json` defines every rate once. The vector is written with the textbook expressions (tests/formulas/generate.py), independent
// of the registry, and Python (`tests/test_formulas.py`) answers the same.
describe.each(vector.cases)('the formulas of the registry: $name', c => {
  it('every formula gives the textbook value, null when a denominator is 0', () => {
    const got = evaluateAll(c.counters as Counters)
    expect(Object.keys(got).sort()).toEqual(Object.keys(c.expected).sort())
    for (const [name, want] of Object.entries(c.expected)) {
      if (want === null) expect(got[name], name).toBeNull()
      else expect(got[name] as number, name).toBeCloseTo(want as number, 9)
    }
  })
})

describe('the registry', () => {
  it('reads the same definitions as Python: every counter and the six rates that used to differ', () => {
    expect(COUNTERS).toContain('opp_poss')
    expect(Object.keys(FORMULAS['steal_rate'].den as object)).toEqual(['opp_poss'])
    expect(FORMULAS['turnover_rate'].den).toEqual({ fg2a: 1, fg3a: 1, fta: 0.44, tov: 1 })
  })

  it('an unknown counter is an error, not a zero', () => {
    expect(() => evaluate('turnover_rate', { tov: 1 } as unknown as Counters)).toThrow()
  })
})
