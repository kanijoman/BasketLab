/**
 * EvolutionPage — Fase 3
 * Evolución temporal de métricas con Recharts multi-equipo/multi-stat + brush zoom.
 */
import { TrendingUp } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'

export default function EvolutionPage() {
  const { collection } = useCollection()
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Evolución Temporal</h1>
          <p className="text-ink-secondary text-sm mt-1">{collection?.label}</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <TrendingUp className="w-10 h-10 text-accent-400 opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 3</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Gráficas de progresión por equipo y métrica con Recharts, rolling average
            y brush/zoom sobre el eje temporal.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
