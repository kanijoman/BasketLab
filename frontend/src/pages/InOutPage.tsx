/**
 * InOutPage — Fase 4
 * Impacto de jugadores dentro/fuera de la cancha con cards ON/OFF.
 */
import { ArrowLeftRight } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'

export default function InOutPage() {
  const { collection } = useCollection()
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Análisis IN/OUT</h1>
          <p className="text-ink-secondary text-sm mt-1">{collection?.label}</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <ArrowLeftRight className="w-10 h-10 text-brand-400 opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 4</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Cards ON/OFF con delta bars coloreadas. Tab de compañeros (Inv IN)
            y comparativa entre dos jugadores con impacto diferencial.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
