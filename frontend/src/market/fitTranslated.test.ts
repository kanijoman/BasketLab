import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/equivalence.json'
import { estimateFromDocument, type EquivalenceDocument, type EstimateOrigin } from './equivalence'
import { fitIn } from './fit'
import { fitTranslated, steadyAxes, translatedCandidate } from './fitTranslated'
import { COVER_PCT, valueOf, AXES } from './myTeam'
import { RADAR_AXES } from './player'
import type { SearchRow } from './search'

/** The fit of a player of another competition (#891, E4c): his percentiles are translated to the competition of the team with the estimator of the equivalences, over the REAL document of the exporter. */
const doc = vectors.document as unknown as EquivalenceDocument
type Case = { history: EstimateOrigin[]; to: string; estimate: unknown[] | null }
const sample = (vectors.cases as unknown as Case[]).find(c => c.estimate)!
const base = { person_id: 'feb:1', name: 'A', full_name: null, team_id: '1', team_name: 'T', minutes: 900, eligible: true, comp_key: 'x', competition: 'x', season: '2025', season_label: '2025', age: 22, linked_to: null,
  pct: { pts: 50, ast: 50, orb: 50, drb: 50, stl: 50, blk: 50, efg: 50, tov: 50 } } as unknown as SearchRow

describe('the candidate translated to the competition of the team', () => {
  it('has the centre of the estimate as percentiles and its low end in `low`, and keeps everything else of the row', () => {
    const t = translatedCandidate(doc, sample.history, base, sample.to)!
    const want = estimateFromDocument(doc, sample.history, sample.to)!
    RADAR_AXES.forEach((a, i) => {
      expect(t.row.pct![a.key as 'pts']).toBeCloseTo(want[i].pct_mean, 9)
      expect(t.low.pct![a.key as 'pts']).toBeCloseTo(want[i].pct_lo, 9)
      expect(t.low.pct![a.key as 'pts']).toBeLessThanOrEqual(t.row.pct![a.key as 'pts'] as number)
    })
    expect(t.row.person_id).toBe(base.person_id)
    expect(t.row.minutes).toBe(base.minutes)
    expect(t.seasons).toBe(want[0].seasons)
    expect(base.pct!.pts).toBe(50)                                  // the original row is not touched
  })

  it('is null when the competition cannot be reached from the one of the player or he has no history', () => {
    expect(translatedCandidate(doc, sample.history, base, 'F|feb|NO SUCH LEVEL')).toBeNull()
    expect(translatedCandidate(doc, [], base, sample.to)).toBeNull()
  })

  it('says the axes where he stands out that hold even at the low end of the range', () => {
    const t = translatedCandidate(doc, sample.history, base, sample.to)!
    const rotation = Array.from({ length: 8 }, (_, i) => ({ ...base, person_id: `feb:${100 + i}`, team_id: '9', pct: { pts: 10, ast: 10, orb: 10, drb: 10, stl: 10, blk: 10, efg: 10, tov: 10 } }) as unknown as SearchRow)
    const fit = fitIn(rotation, t.row)
    const steady = steadyAxes(fit, t.low)
    const standing = [...fit.fills, ...fit.collides.map(c => c.axis)].map(a => a.key)
    expect(steady.every(k => standing.includes(k))).toBe(true)
    for (const k of steady) expect(valueOf(t.low, AXES.find(a => a.key === k)!.parts)!).toBeGreaterThanOrEqual(COVER_PCT)
  })

  describe('the fit that chooses', () => {
    const rotation = Array.from({ length: 8 }, (_, i) => ({ ...base, person_id: `feb:${100 + i}`, team_id: '9', comp_key: 'team', pct: { pts: 10, ast: 10, orb: 10, drb: 10, stl: 10, blk: 10, efg: 10, tov: 10 } }) as unknown as SearchRow)

    it('judges his own percentiles when he plays in the competition of the team, whatever the document says', () => {
      const r = fitTranslated(rotation, { ...base, comp_key: 'team' }, 'team', sample.to, doc, sample.history)
      expect(r.translated).toBeNull()
      expect(r.steady).toEqual([])
    })

    it('translates when he is from another competition and a translation exists, and judges the translated profile', () => {
      const r = fitTranslated(rotation, base, 'team', sample.to, doc, sample.history)
      const t = translatedCandidate(doc, sample.history, base, sample.to)!
      expect(r.translated?.to).toBe(sample.to)
      expect(r.fit).toEqual(fitIn(rotation, t.row))
    })

    it('falls back to his own percentiles, said by `translated: null`, without document, without node or without a translation', () => {
      for (const [d, node] of [[null, sample.to], [doc, null], [doc, 'F|feb|NO SUCH LEVEL']] as const) {
        const r = fitTranslated(rotation, base, 'team', node, d, sample.history)
        expect(r.translated).toBeNull()
        expect(r.fit).toEqual(fitIn(rotation, base))
      }
    })
  })
})
