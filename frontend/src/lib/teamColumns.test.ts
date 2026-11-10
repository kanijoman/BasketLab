import { describe, expect, it } from 'vitest'
import { BASIC_COL_DEFS, MULTIPHASE_BASIC_COL_DEFS } from './teamColumns'

describe('teamColumns', () => {
  it('the multiphase table is the basic one without the home/away split (no duplicated definition, #452)', () => {
    const keys = MULTIPHASE_BASIC_COL_DEFS.map(d => d.key)
    expect(keys).not.toContain('games_home')
    expect(keys).not.toContain('games_away')
    expect(keys).toHaveLength(BASIC_COL_DEFS.length - 2)
    // The same column object, so a header or a width changed in one place changes everywhere
    for (const def of MULTIPHASE_BASIC_COL_DEFS) expect(BASIC_COL_DEFS).toContain(def)
  })
})
