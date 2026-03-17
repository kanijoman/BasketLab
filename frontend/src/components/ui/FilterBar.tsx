/**
 * FilterBar — venue / result / date range filters.
 *
 * State is persisted in URL search params so filters survive navigation
 * and are shareable via URL.
 *
 * Usage:
 *   const filters = useFilters()  // reads from URL
 *   <FilterBar />                 // renders + updates URL
 */
import { useSearchParams } from 'react-router-dom'
import { Filter, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface Filters {
  venue: '' | 'home' | 'away'
  result: '' | 'won' | 'lost'
  dateFrom: string
  dateTo: string
}

/** Hook to read current filters from URL search params */
export function useFilters(): Filters {
  const [params] = useSearchParams()
  return {
    venue:    (params.get('venue')  ?? '') as Filters['venue'],
    result:   (params.get('result') ?? '') as Filters['result'],
    dateFrom: params.get('from') ?? '',
    dateTo:   params.get('to')   ?? '',
  }
}

/** Returns true if any filter is active */
export function hasActiveFilters(f: Filters): boolean {
  return Boolean(f.venue || f.result || f.dateFrom || f.dateTo)
}

interface ToggleGroupProps<T extends string> {
  label: string
  value: T
  options: { label: string; value: T }[]
  onChange: (v: T) => void
}

function ToggleGroup<T extends string>({ label, value, options, onChange }: ToggleGroupProps<T>) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-xs text-ink-muted mr-1 hidden sm:block">{label}</span>
      <div className="flex rounded-lg overflow-hidden border border-surface-border">
        {options.map(opt => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value === value ? '' as T : opt.value)}
            className={cn(
              'px-2.5 py-1 text-xs font-medium transition-colors',
              value === opt.value
                ? 'bg-brand-600/30 text-brand-400 border-brand-600/40'
                : 'text-ink-secondary hover:bg-surface-hover hover:text-ink-primary',
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

interface Props {
  showDate?: boolean
  className?: string
}

export default function FilterBar({ showDate = true, className }: Props) {
  const [params, setParams] = useSearchParams()

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const clearAll = () => setParams({}, { replace: true })

  const venue  = (params.get('venue')  ?? '') as Filters['venue']
  const result = (params.get('result') ?? '') as Filters['result']
  const from   = params.get('from') ?? ''
  const to     = params.get('to')   ?? ''
  const active = Boolean(venue || result || from || to)

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <Filter className="w-3.5 h-3.5 text-ink-muted shrink-0" />

      <ToggleGroup
        label="Campo"
        value={venue}
        options={[
          { label: 'Local', value: 'home' },
          { label: 'Visitante', value: 'away' },
        ]}
        onChange={v => setParam('venue', v)}
      />

      <ToggleGroup
        label="Resultado"
        value={result}
        options={[
          { label: 'Victoria', value: 'won' },
          { label: 'Derrota', value: 'lost' },
        ]}
        onChange={v => setParam('result', v)}
      />

      {showDate && (
        <div className="flex flex-wrap items-center gap-1">
          {/* Quick date presets */}
          {([7, 15, 30, 60] as const).map(n => {
            const d = new Date()
            d.setDate(d.getDate() - n)
            const iso = d.toISOString().slice(0, 10)
            const active7 = from === iso && !to
            return (
              <button
                key={n}
                onClick={() => { setParam('from', iso); setParam('to', '') }}
                className={cn(
                  'px-2 py-0.5 rounded text-xs border transition-colors',
                  active7
                    ? 'bg-brand-600/30 text-brand-400 border-brand-600/40'
                    : 'border-surface-border text-ink-secondary hover:text-ink-primary',
                )}
              >
                {n}d
              </button>
            )
          })}
          <input
            type="date"
            value={from}
            onChange={e => setParam('from', e.target.value)}
            className="input !w-auto text-xs py-1 px-2"
            aria-label="Desde"
            title="Desde"
          />
          <span className="text-ink-muted text-xs">–</span>
          <input
            type="date"
            value={to}
            onChange={e => setParam('to', e.target.value)}
            className="input !w-auto text-xs py-1 px-2"
            aria-label="Hasta"
            title="Hasta"
          />
        </div>
      )}

      {active && (
        <button
          onClick={clearAll}
          className="btn-ghost text-xs text-ink-muted"
          title="Borrar filtros"
        >
          <X className="w-3 h-3" /> Borrar
        </button>
      )}
    </div>
  )
}
