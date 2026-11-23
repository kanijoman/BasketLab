import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/formation.json'
import type { EquivalenceDocument } from './equivalence'
import { estimateFormation, formationOf, type FormationDocument, type FormationObs, type FormationRow } from './formation'

/** Parity with Python (#893, E3c): the estimate of a player of the formation rebuilt from the two published documents must be the one `formation_publish.estimate_from_documents` gives, and his history from the raw rows the one of `formation_observations`. */
const document = vectors.formation as unknown as FormationDocument
const equivalences = vectors.equivalences as unknown as EquivalenceDocument
type Case = { history: FormationObs[]; to: string; estimate: Record<string, number | string>[] | null }
const cases = vectors.cases as unknown as Case[]

describe('the estimate of a player of the formation from the documents', () => {
  it('has cases with and without an estimate', () => {
    expect(cases.some(c => c.estimate)).toBe(true)
    expect(cases.some(c => c.estimate === null)).toBe(true)
  })

  it('matches Python on every case', () => {
    for (const c of cases) {
      const got = estimateFormation(document, equivalences, c.history, c.to)
      if (c.estimate === null) { expect(got).toBeNull(); continue }
      expect(got).not.toBeNull()
      c.estimate.forEach((want, i) => {
        for (const key of ['mean', 'lo', 'hi', 'sd', 'pct_lo', 'pct_mean', 'pct_hi'] as const) expect(got![i][key]).toBeCloseTo(want[key] as number, 9)
        expect(got![i].group).toBe(want.group)
        expect(got![i].season).toBe(want.season)
      })
    }
  })

  it('has no estimate without formation, for a group the index does not speak of or for a competition outside the graph', () => {
    const one = cases.find(c => c.estimate)!
    expect(estimateFormation(document, equivalences, [], one.to)).toBeNull()
    expect(estimateFormation(document, equivalences, [{ ...one.history[0], group: 'U12' }], one.to)).toBeNull()
    expect(estimateFormation(document, equivalences, one.history, 'F|feb|NO SUCH LEVEL')).toBeNull()
  })
})

describe('the formation history of a player from his rows', () => {
  type History = { rows: (FormationRow['row'] & { comp: string })[]; competitions: Record<string, FormationRow['entry']>; expected: FormationObs[] }
  const histories = vectors.histories as unknown as History[]

  it('is what Python makes of the same rows (the best row of each group and season, the z of the percentiles, only the formation of FEB)', () => {
    for (const h of histories) {
      const got = formationOf(h.rows.map(row => ({ entry: h.competitions[row.comp], row })))
      expect(got.map(o => [o.season, o.group, o.sex, o.minutes])).toEqual(h.expected.map(o => [o.season, o.group, o.sex, o.minutes]))
      got.forEach((o, i) => o.z.forEach((v, k) => expect(v).toBeCloseTo(h.expected[i].z[k], 9)))
    }
  })

  it('leaves out a row that did not play enough, one with an axis missing, FBCYL and what is not formation', () => {
    const entry = { competition: 'CE U18', league: 'feb', gender: 'F', category: 'formacion', age_group: 'U18', season: '2024' } as FormationRow['entry']
    const pct = { pts: 50, ast: 50, orb: 50, drb: 50, stl: 50, blk: 50, efg: 50, tov: 50 }
    const row = { person_id: 'feb:1', linked_to: null, minutes: 600, eligible: true, pct }
    expect(formationOf([{ entry, row }])).toHaveLength(1)
    expect(formationOf([{ entry, row: { ...row, eligible: false } }])).toHaveLength(0)
    expect(formationOf([{ entry, row: { ...row, pct: { ...pct, blk: null } } }])).toHaveLength(0)
    expect(formationOf([{ entry: { ...entry, league: 'fbcyl' }, row }])).toHaveLength(0)
    expect(formationOf([{ entry: { ...entry, category: 'senior' }, row }])).toHaveLength(0)
  })
})
