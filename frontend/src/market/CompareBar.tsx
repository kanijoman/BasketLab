// The bar of the players ticked to compare (#1009): how many, the way to the comparator with them chosen, and the way to clear the selection. It appears only when something is ticked, stays at the
// bottom of the screen while the list scrolls, and says why a fourth cannot be ticked. The selection itself lives in `SearchPage` (remembered by `compareMemory`).
import { Link } from 'react-router-dom'
import { Scale } from 'lucide-react'
import Button from '@/components/ui/Button'
import { MAX_COMPARED } from './compare'

export default function CompareBar({ ids, onClear }: { ids: string[]; onClear: () => void }) {
  if (ids.length === 0) return null
  const enough = ids.length >= 2
  return (
    <section aria-label="Selección para comparar" className="sticky bottom-3 z-20 flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface px-4 py-2.5 shadow-panel">
      <p className="text-sm text-ink">
        {ids.length} {ids.length === 1 ? 'jugador elegido' : 'jugadores elegidos'}
        {ids.length >= MAX_COMPARED && <span className="ml-2 text-xs text-ink-muted">Máximo {MAX_COMPARED} jugadores</span>}
        {!enough && <span className="ml-2 text-xs text-ink-muted">Elige al menos otro</span>}
      </p>
      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onClear}>Quitar la selección</Button>
        {enough
          ? <Link to={`/comparar?j=${encodeURIComponent(ids.join(','))}`} className="btn-primary inline-flex items-center gap-1.5 text-sm"><Scale className="h-4 w-4" aria-hidden="true" />Comparar {ids.length} jugadores</Link>
          : <Link to={`/comparar?j=${encodeURIComponent(ids.join(','))}`} className="text-sm font-medium text-accent-text hover:underline">Abrir en el comparador</Link>}
      </div>
    </section>
  )
}
