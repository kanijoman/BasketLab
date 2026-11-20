// The index of the formation in the browser (#893, E3c): what a player of the formation would be in a senior competition IF he gets there, with the 80 % range. A port of `formation_publish.estimate_from_documents`
// and `formation.formation_observations` (Python is the reference; `tests/local_vectors/formation.json` pins the parity). Conditional on getting there: the page says it.
import { phi } from '@/forecast/normal'
import { Z80, zOf, type EquivalenceDocument } from './equivalence'

export interface FormationDocument {
  format: number
  axes: string[]
  groups: string[]
  sexes: Record<string, { coef: number[][]; sigma: number[]; n: number }>
  validation: { n: number; mae_model: number | null; mae_mean: number | null; coverage: number | null; publish: boolean }
  usable: boolean
}

/** One season of a player of the formation in one group: his z per axis. */
export interface FormationObs { season: number; group: string; sex: string; minutes: number; z: number[] }

export interface FormationEstimate {
  mean: number; lo: number; hi: number; sd: number
  pct_lo: number; pct_mean: number; pct_hi: number
  group: string
  season: number
}

/** A row of a person with the competition it belongs to. */
export interface FormationRow {
  entry: { competition: string; league: string; gender?: string; category?: string; age_group?: string | null; season: string }
  row: { person_id: string; linked_to: string | null; minutes: number; eligible: boolean; pct: Record<string, number | null> | null }
}

const AXES = ['pts', 'ast', 'orb', 'drb', 'stl', 'blk', 'efg', 'tov'] as const

/** The formation observations of ONE person (`formation.formation_observations`): one per season, group and sex, the row with more minutes, only the formation of FEB that played enough and has the eight percentiles. */
export function formationOf(rows: FormationRow[]): FormationObs[] {
  const best = new Map<string, { rank: [number, string]; obs: FormationObs }>()
  for (const { entry, row } of rows) {
    const values = AXES.map(a => row.pct?.[a])
    if (entry.category !== 'formacion' || entry.league !== 'feb' || (entry.gender !== 'M' && entry.gender !== 'F') || !entry.age_group || !row.eligible || !values.every((v): v is number => typeof v === 'number')) continue
    const season = Number(entry.season)
    const key = `${season}\u0000${entry.age_group}\u0000${entry.gender}`
    const rank: [number, string] = [Math.trunc(row.minutes || 0), String(row.person_id)]
    const old = best.get(key)
    if (!old || rank[0] > old.rank[0] || (rank[0] === old.rank[0] && rank[1] > old.rank[1])) best.set(key, { rank, obs: { season, group: entry.age_group, sex: entry.gender, minutes: rank[0], z: values.map(zOf) } })
  }
  return [...best.values()].map(b => b.obs).sort((a, b) => a.season - b.season || (a.group < b.group ? -1 : a.group > b.group ? 1 : 0) || (a.sex < b.sex ? -1 : 1))
}

/** What he would be in the senior competition `to` IF he gets there, from his latest formation season; `null` without formation, for a group or sex the index does not speak of or a competition the graph does not know. */
export function estimateFormation(doc: FormationDocument, equivalences: EquivalenceDocument, history: FormationObs[], to: string): FormationEstimate[] | null {
  if (!history.length) return null
  const last = history.reduce((best, o) => (o.season > best.season || (o.season === best.season && (o.minutes > best.minutes || (o.minutes === best.minutes && o.group > best.group))) ? o : best))
  const part = doc.sexes[last.sex]
  const eq = equivalences.sexes[last.sex]
  if (!doc.groups.includes(last.group) || !part || !eq || to.split('|')[0] !== last.sex || !eq.nodes.includes(to)) return null
  const at = eq.nodes.indexOf(to)
  return doc.axes.map((_, i) => {
    const [a, b, g] = part.coef[i]
    const mean = a + b * last.z[i] + g * (last.group === 'U18' ? 1 : 0) + eq.theta[i][at]
    const sd = part.sigma[i]
    const lo = mean - Z80 * sd
    const hi = mean + Z80 * sd
    return { mean, lo, hi, sd, pct_lo: 100 * phi(lo), pct_mean: 100 * phi(mean), pct_hi: 100 * phi(hi), group: last.group, season: last.season }
  })
}
