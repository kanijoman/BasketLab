// The fit of a player of ANOTHER competition (#891, E4c): the fit rules of `fit.ts` judge percentiles of the competition of the team, so the percentiles of the candidate are replaced by what the estimator of the
// equivalences expects in that competition (the centre of its range), and the low end of the range is kept to say which of the verdicts hold even there. Pure functions; the estimate is `equivalence.ts`.
import { estimateFromDocument, type EquivalenceDocument, type EstimateOrigin } from './equivalence'
import { fitIn, type Fit } from './fit'
import { AXES, COVER_PCT, valueOf } from './myTeam'
import { RADAR_AXES } from './player'
import type { SearchRow } from './search'

export interface Translated {
  /** The candidate with the centre of the range as percentiles. */
  row: SearchRow
  /** The candidate with the low end of the range. */
  low: SearchRow
  seasons: 1 | 2
  from: string
  to: string
}

/** The candidate as he would be in `to` (a node of the graph), or null when there is no translation. The row passed is not changed. */
export function translatedCandidate(doc: EquivalenceDocument, history: EstimateOrigin[], row: SearchRow, to: string): Translated | null {
  const estimate = estimateFromDocument(doc, history, to)
  if (!estimate || !row.pct) return null
  const percentiles = (pick: 'pct_mean' | 'pct_lo'): SearchRow['pct'] => ({ ...row.pct!, ...Object.fromEntries(RADAR_AXES.map((a, i) => [a.key, estimate[i][pick]])) })
  return { row: { ...row, pct: percentiles('pct_mean') }, low: { ...row, pct: percentiles('pct_lo') }, seasons: estimate[0].seasons, from: estimate[0].from_node, to }
}

/** The axes of the verdict (where he fills a hole or collides) in which he still stands out at the low end of the range. */
export function steadyAxes(fit: Fit, low: SearchRow): string[] {
  const keys = [...fit.fills.map(a => a.key), ...fit.collides.map(c => c.axis.key)]
  return keys.filter(k => (valueOf(low, AXES.find(a => a.key === k)!.parts) ?? -1) >= COVER_PCT)
}

export interface TranslatedFit {
  fit: Fit
  /** Set when the percentiles were translated to the competition of the team (the candidate is from another one); null when the fit judges his own. */
  translated: Translated | null
  /** The axes of the verdict that hold at the low end of the range (empty when nothing was translated). */
  steady: string[]
}

/** The fit of `row` with `rotation` of a team of the competition `teamComp` (node `teamNode`): his own percentiles when he plays in that competition or no translation exists; otherwise the translated ones. */
export function fitTranslated(rotation: SearchRow[], row: SearchRow, teamComp: string, teamNode: string | null, doc: EquivalenceDocument | null | undefined, history: EstimateOrigin[]): TranslatedFit {
  const translated = doc && teamNode && row.comp_key !== teamComp ? translatedCandidate(doc, history, row, teamNode) : null
  const fit = fitIn(rotation, translated ? translated.row : row)
  return { fit, translated, steady: translated ? steadyAxes(fit, translated.low) : [] }
}
