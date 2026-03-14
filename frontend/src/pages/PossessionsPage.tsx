/**
 * PossessionsPage — Fase 3
 * Ritmo, OER/DER y scatter Ritmo×OER con cuatro cuadrantes.
 */
import { Activity } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'

export default function PossessionsPage() {
  const { collection } = useCollection()
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Análisis de Posesiones</h1>
          <p className="text-ink-secondary text-sm mt-1">{collection?.label}</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <Activity className="w-10 h-10 text-accent-400 opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 3</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Tabla con cuartiles de posesiones, OER y DER. Scatter Ritmo×OER
            con cuatro cuadrantes (rápido-eficiente, lento-ineficiente, etc.).
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
