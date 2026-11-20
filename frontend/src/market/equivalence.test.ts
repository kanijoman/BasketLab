import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/equivalence.json'
import { estimateFromDocument, type EquivalenceDocument, type EstimateOrigin } from './equivalence'

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
