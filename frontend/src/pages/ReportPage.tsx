/**
 * ReportPage — Fase 5
 * Wizard multi-paso para generación de informes semanales (PDF/DOCX).
 */
import { FileText } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'

export default function ReportPage() {
  const { collection } = useCollection()
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Informe Semanal</h1>
          <p className="text-ink-secondary text-sm mt-1">{collection?.label}</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <FileText className="w-10 h-10 text-warn opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 5</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Wizard multi-paso: selección de equipos → secciones a incluir → preview web →
            export PDF o DOCX generado por el backend.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
