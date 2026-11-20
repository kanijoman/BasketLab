import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/equivalence.json'
import { estimateFromDocument, historyOf, type EquivalenceDocument, type EstimateOrigin, type HistoryRow } from './equivalence'

/** Parity with Python (#891, E1c/E4): the single estimate of a player rebuilt from the published `equivalences` document must be the one `equivalence_publish.estimate_from_document` gives. */
const doc = vectors.document as unknown as EquivalenceDocument
type Case = { history: EstimateOrigin[]; to: string; estimate: Record<string, number | string>[] | null }
const cases = vectors.cases as unknown as Case[]

describe('the estimate of a player from the document', () => {
  it('has cases of one and of two seasons and of no estimate', () => {
    expect(cases.some(c => c.estimate?.[0].seasons === 1)).toBe(true)
    expect(cases.some(c => c.estimate?.[0].seasons === 2)).toBe(true)
    expect(cases.some(c => c.estimate === null)).toBe(true)
  })

  it('matches Python on every case', () => {
    for (const c of cases) {
      const got = estimateFromDocument(doc, c.history, c.to)
      if (c.estimate === null) { expect(got).toBeNull(); continue }
      expect(got).not.toBeNull()
      c.estimate.forEach((want, i) => {
        for (const key of ['mean', 'lo', 'hi', 'sd', 'se_level', 'pct_lo', 'pct_mean', 'pct_hi'] as const) expect(got![i][key]).toBeCloseTo(want[key] as number, 9)
        expect(got![i].seasons).toBe(want.seasons)
        expect(got![i].from_node).toBe(want.from_node)
      })
    }
  })

  it('has no estimate without history', () => {
    expect(estimateFromDocument(doc, [], 'F|feb|LF CHALLENGE')).toBeNull()
  })
})

describe('the history of a player from his rows', () => {
  type History = { rows: (HistoryRow['row'] & { comp: string })[]; competitions: Record<string, HistoryRow['entry']>; expected: EstimateOrigin[] }
  const histories = vectors.histories as unknown as History[]

  it('is what Python makes of the same rows (the best row of each competition and season, the z of the percentiles, no cup and no formation)', () => {
    expect(histories.some(h => h.rows.length > h.expected.length)).toBe(true)
    for (const h of histories) {
      const got = historyOf(h.rows.map(row => ({ entry: h.competitions[row.comp], row })))
      expect(got.map(o => [o.node, o.season, o.minutes])).toEqual(h.expected.map(o => [o.node, o.season, o.minutes]))
      got.forEach((o, i) => o.z.forEach((v, k) => expect(v).toBeCloseTo(h.expected[i].z[k], 9)))
    }
  })

  it('leaves out a row that did not play enough, one with an axis missing and a competition that is not a level', () => {
    const entry = { competition: 'LF CHALLENGE', league: 'feb', gender: 'F', category: 'senior', season: '2025' } as HistoryRow['entry']
    const pct = { pts: 50, ast: 50, orb: 50, drb: 50, stl: 50, blk: 50, efg: 50, tov: 50 }
    const row = { person_id: 'feb:1', linked_to: null, minutes: 600, eligible: true, pct }
    expect(historyOf([{ entry, row }])).toHaveLength(1)
    expect(historyOf([{ entry, row: { ...row, eligible: false } }])).toHaveLength(0)
    expect(historyOf([{ entry, row: { ...row, pct: { ...pct, blk: null } } }])).toHaveLength(0)
    expect(historyOf([{ entry: { ...entry, competition: 'COPA DE LA REINA' }, row }])).toHaveLength(0)
    expect(historyOf([{ entry: { ...entry, category: 'formacion' }, row }])).toHaveLength(0)
    expect(historyOf([{ entry: { ...entry, league: 'fbcyl' }, row }])).toHaveLength(0)
  })
})
