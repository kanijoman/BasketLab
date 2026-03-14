/**
 * ShotChartPage — Fase 3
 * Cancha FIBA SVG interactiva con D3.js, heatmap de zonas y scatter de tiros.
 */
import { Target } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'

export default function ShotChartPage() {
  const { collection } = useCollection()
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Gráficos de Tiro</h1>
          <p className="text-ink-secondary text-sm mt-1">{collection?.label}</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <Target className="w-10 h-10 text-accent-400 opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 3</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Cancha FIBA renderizada en SVG con D3.js. 10 zonas interactivas: heatmap de
            eficiencia, scatter de tiros individuales (anotados/fallados), vista equipo/jugador.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
