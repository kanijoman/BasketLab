// The filters of the search that are ON, as chips that can be taken off one by one (#1008), and the order of the list. Plain functions (no React). The words are those of the panel.
import { GROUP_LABELS } from './groupLabels'
import { METRICS, type SearchFilters, type SearchRow } from './search'

export type FilterKey = 'text' | 'age' | 'height' | 'groups' | 'metric' | 'eligible' | 'unknown'
export interface Chip { key: FilterKey; label: string }

const range = (min: number | null, max: number | null, unit = ''): string | null =>
  min !== null && max !== null ? `${min} a ${max}${unit}` : min !== null ? `desde ${min}${unit}` : max !== null ? `hasta ${max}${unit}` : null

/** One chip per filter that is on, in a fixed order (what the panel shows, top to bottom). A zero is a limit like any other. */
export function activeFilters(f: SearchFilters): Chip[] {
  const chips: Chip[] = []
  if (f.text.trim()) chips.push({ key: 'text', label: `Nombre: ${f.text.trim()}` })
  const age = range(f.ageMin, f.ageMax)
  if (age) chips.push({ key: 'age', label: `Edad: ${age}` })
  const height = range(f.heightMin, f.heightMax, ' cm')
  if (height) chips.push({ key: 'height', label: `Altura: ${height}` })
  if (f.groups.length) chips.push({ key: 'groups', label: `Posición: ${f.groups.map(g => GROUP_LABELS[g].toLowerCase()).join(', ')}` })
  if (f.metric) chips.push({ key: 'metric', label: `${METRICS.find(m => m.key === f.metric)?.label ?? f.metric}${f.pctMin !== null ? ` desde el percentil ${f.pctMin}` : ''}` })
  if (f.onlyEligible) chips.push({ key: 'eligible', label: 'Solo con minutos suficientes' })
  if (f.includeUnknown) chips.push({ key: 'unknown', label: 'Con los que no tienen el dato' })
  return chips
}

/** The filters without the one of ``key`` (the percentile goes with its metric). The input is not changed. */
export function withoutFilter(f: SearchFilters, key: FilterKey): SearchFilters {
  switch (key) {
    case 'text': return { ...f, text: '' }
    case 'age': return { ...f, ageMin: null, ageMax: null }
    case 'height': return { ...f, heightMin: null, heightMax: null }
    case 'groups': return { ...f, groups: [] }
    case 'metric': return { ...f, metric: '', pctMin: null }
    case 'eligible': return { ...f, onlyEligible: false }
    case 'unknown': return { ...f, includeUnknown: false }
  }
}

/** The list by minutes played, the most first; a tie by name and team, so the order never depends on how the rows came. A copy: the input is not changed. */
export const byMinutes = <T extends Pick<SearchRow, 'full_name' | 'name' | 'team_name' | 'minutes'>>(rows: T[]): T[] =>
  [...rows].sort((a, b) => b.minutes - a.minutes || (a.full_name ?? a.name).localeCompare(b.full_name ?? b.name) || a.team_name.localeCompare(b.team_name))
