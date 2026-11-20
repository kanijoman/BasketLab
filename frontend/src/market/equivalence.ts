// The estimate of a player in another competition (#891, E1c/E4): what the browser does with the published `equivalences` document. A port of
// `equivalence_publish.estimate_from_document` (Python is the reference; `tests/local_vectors/equivalence.json` pins the parity). ONE estimate per player: which reliability applies (one season or two) is decided here, never by the caller.
import { phi } from '@/forecast/normal'

/** The half width of an 80 % interval in standard deviations (`NormalDist().inv_cdf(0.9)`). */
export const Z80 = 1.2815515655446004

export interface EquivalenceSex {
  nodes: string[]
  component: number[]
  rho: number[]
  sigma: number[]
  theta: number[][]
  cov: number[][][]
  two: { rho: number[]; sigma: number[] } | null
}

export interface EquivalenceDocument {
  format: number
  axes: string[]
  sexes: Record<string, EquivalenceSex>
  edges: { from: string; to: string; persons: number; moves: number }[]
  validation: { n: number; mae_model: number | null; mae_identity: number | null; coverage: number | null; publish: boolean }
  usable: boolean
}

/** One season of a person in one competition: the node (`F|feb|LF CHALLENGE`), the season, his minutes and his z per axis. */
export interface EstimateOrigin { node: string; season: number; minutes: number; z: number[] }

export interface AxisEstimate {
  mean: number; lo: number; hi: number; sd: number; se_level: number
  pct_lo: number; pct_mean: number; pct_hi: number
  seasons: 1 | 2
  from_node: string
}

/** His latest competition and the z to translate: the average by minutes of his latest season and the one before in the same competition, or the latest alone. */
export function origin(history: EstimateOrigin[]): { last: EstimateOrigin; z: number[]; seasons: 1 | 2 } | null {
  if (!history.length) return null
  const latest = Math.max(...history.map(o => o.season))
  const last = history.filter(o => o.season === latest).reduce((best, o) => (o.minutes > best.minutes || (o.minutes === best.minutes && o.node > best.node) ? o : best))
  const previous = history.find(o => o.node === last.node && o.season === latest - 1)
  if (!previous) return { last, z: last.z, seasons: 1 }
  const [wa, wb] = last.minutes + previous.minutes > 0 ? [last.minutes, previous.minutes] : [1, 1]
  return { last, z: last.z.map((v, i) => (wa * v + wb * previous.z[i]) / (wa + wb)), seasons: 2 }
}

/** What he would be expected to do in `to`, per axis, with the 80 % range; `null` without history, without a graph for that sex or when the two competitions are not connected. */
export function estimateFromDocument(doc: EquivalenceDocument, history: EstimateOrigin[], to: string): AxisEstimate[] | null {
  const start = origin(history)
  if (!start) return null
  const { last, z, seasons } = start
  const sex = last.node.split('|')[0]
  const part = doc.sexes[sex]
  if (!part || to.split('|')[0] !== sex) return null
  const a = part.nodes.indexOf(last.node)
  const b = part.nodes.indexOf(to)
  if (a < 0 || b < 0 || part.component[a] !== part.component[b]) return null
  const kept = seasons === 2 ? part.two : null
  const rho = kept ? kept.rho : part.rho
  const sigma = kept ? kept.sigma : part.sigma
  return doc.axes.map((_, i) => {
    const cov = part.cov[i]
    const variance = Math.max(cov[b][b] + cov[a][a] - 2 * cov[a][b], 0)
    const mean = rho[i] * z[i] + part.theta[i][b] - part.theta[i][a]
    const sd = Math.sqrt(sigma[i] ** 2 + variance)
    const lo = mean - Z80 * sd
    const hi = mean + Z80 * sd
    return { mean, lo, hi, sd, se_level: Math.sqrt(variance), pct_lo: 100 * phi(lo), pct_mean: 100 * phi(mean), pct_hi: 100 * phi(hi), seasons, from_node: last.node }
  })
}
