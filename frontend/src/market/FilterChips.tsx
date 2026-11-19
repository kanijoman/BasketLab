// The filters that are on, as chips next to the result (#1008): each one is taken off with a click, and «Limpiar filtros» takes them all off. On a phone, where the panel is closed, it is how the staff
// sees what the list is filtered by. The words and the rules are in `activeFilters.ts`.
import { X } from 'lucide-react'
import Button from '@/components/ui/Button'
import { activeFilters, withoutFilter } from './activeFilters'
import { NO_FILTERS, type SearchFilters } from './search'

export default function FilterChips({ filters, onFilters }: { filters: SearchFilters; onFilters: (filters: SearchFilters) => void }) {
  const chips = activeFilters(filters)
  if (chips.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2">
      <ul aria-label="Filtros activos" className="flex flex-wrap gap-2">
        {chips.map(c => (
          <li key={c.key} className="flex items-center gap-1 rounded-full border border-line bg-surface py-0.5 pl-3 pr-1 text-xs text-ink">
            {c.label}
            <Button variant="ghost" size="sm" icon={X} aria-label={`Quitar el filtro ${c.label}`} className="!px-1.5 !py-1" onClick={() => onFilters(withoutFilter(filters, c.key))} />
          </li>
        ))}
      </ul>
      <Button variant="ghost" size="sm" onClick={() => onFilters(NO_FILTERS)}>Limpiar filtros</Button>
    </div>
  )
}
