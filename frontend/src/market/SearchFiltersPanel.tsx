// The filters of the Talent search (B3, #879): what to ask, in the words of the staff. The state lives in the address (`SearchPage`), so a search is shared with a link.
import Button from '@/components/ui/Button'
import Card from '@/components/ui/Card'
import Checkbox from '@/components/ui/Checkbox'
import { Field, Input, Select } from '@/components/ui/Field'
import type { TalentCompetitionEntry } from './data'
import { METRICS, mixNotice, NO_FILTERS, type Metric, type PositionGroup, type SearchFilters } from './search'
import { AlertTriangle } from 'lucide-react'

const GROUP_LABELS: Record<PositionGroup, string> = { G: 'Bases y escoltas', F: 'Aleros y ala-pívots', C: 'Pívots' }

const numberOrNull = (text: string): number | null => (text.trim() === '' || !Number.isFinite(Number(text)) ? null : Number(text))

interface NumberFieldProps { label: string; value: number | null; onChange: (value: number | null) => void; min?: number; max?: number }

function NumberField({ label, value, onChange, min, max }: NumberFieldProps) {
  return (
    <Field label={label}>
      <Input type="number" inputMode="numeric" min={min} max={max} value={value ?? ''} onChange={e => onChange(numberOrNull(e.target.value))} />
    </Field>
  )
}

interface Props {
  seasons: { value: string; label: string }[]
  season: string
  onSeason: (season: string) => void
  competitions: TalentCompetitionEntry[]
  chosen: string[]
  onChosen: (keys: string[]) => void
  filters: SearchFilters
  onFilters: (filters: SearchFilters) => void
}

export default function SearchFiltersPanel({ seasons, season, onSeason, competitions, chosen, onChosen, filters, onFilters }: Props) {
  const set = (patch: Partial<SearchFilters>) => onFilters({ ...filters, ...patch })
  const toggle = (key: string) => onChosen(chosen.includes(key) ? chosen.filter(k => k !== key) : [...chosen, key])
  const toggleGroup = (g: PositionGroup) => set({ groups: filters.groups.includes(g) ? filters.groups.filter(x => x !== g) : [...filters.groups, g] })
  const notice = mixNotice(competitions.filter(c => chosen.includes(c.key)))
  const active = JSON.stringify(filters) !== JSON.stringify(NO_FILTERS)
  return (
    <Card title="Filtros">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Temporada">
          <Select options={seasons} value={season} onChange={e => onSeason(e.target.value)} />
        </Field>
        <Field label="Jugador o equipo">
          <Input type="search" value={filters.text} onChange={e => set({ text: e.target.value })} placeholder="Nombre, apellido o equipo" />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <NumberField label="Edad mínima" value={filters.ageMin} onChange={ageMin => set({ ageMin })} min={0} max={70} />
          <NumberField label="Edad máxima" value={filters.ageMax} onChange={ageMax => set({ ageMax })} min={0} max={70} />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <NumberField label="Altura mínima (cm)" value={filters.heightMin} onChange={heightMin => set({ heightMin })} min={100} max={260} />
          <NumberField label="Altura máxima (cm)" value={filters.heightMax} onChange={heightMax => set({ heightMax })} min={100} max={260} />
        </div>
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-ink-muted">Posición</p>
          {(Object.keys(GROUP_LABELS) as PositionGroup[]).map(g => (
            <Checkbox key={g} label={GROUP_LABELS[g]} checked={filters.groups.includes(g)} onChange={() => toggleGroup(g)} />
          ))}
        </div>
        <Field label="Percentil en…" hint="Dentro de su competición, entre quienes han jugado lo suficiente">
          <Select value={filters.metric} onChange={e => set({ metric: e.target.value as Metric | '' })}>
            <option value="">Sin filtro de percentil</option>
            {METRICS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
          </Select>
        </Field>
        <NumberField label="Percentil mínimo" value={filters.pctMin} onChange={pctMin => set({ pctMin })} min={0} max={100} />
        <div className="space-y-1.5">
          <Checkbox label="Solo con minutos suficientes" checked={filters.onlyEligible} onChange={e => set({ onlyEligible: e.target.checked })} />
          <Checkbox label="Incluir los que no tienen el dato" checked={filters.includeUnknown} onChange={e => set({ includeUnknown: e.target.checked })} />
          {active && <Button variant="ghost" size="sm" onClick={() => onFilters(NO_FILTERS)}>Limpiar filtros</Button>}
        </div>
      </div>
      <fieldset className="mt-4 space-y-1.5">
        <legend className="text-xs font-medium text-ink-muted">Competiciones de la temporada</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {competitions.map(c => (
            <Checkbox key={c.key} label={`${c.competition} (${c.players})`} checked={chosen.includes(c.key)} onChange={() => toggle(c.key)} />
          ))}
        </div>
      </fieldset>
      {notice && (
        <p role="note" className="mt-3 flex items-start gap-2 rounded-card border border-warn/40 bg-warn/10 px-3 py-2 text-xs text-ink">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden="true" />{notice}
        </p>
      )}
    </Card>
  )
}
