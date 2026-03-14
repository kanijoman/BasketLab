/**
 * AIAnalysisPage — Fase 4
 * Análisis IA con streaming SSE, react-markdown y export PDF/DOCX.
 */
import { Bot } from 'lucide-react'
import PageTransition from '@/components/ui/PageTransition'
import { useCollection } from '@/context/CollectionContext'

export default function AIAnalysisPage() {
  const { collection } = useCollection()
  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Análisis IA</h1>
          <p className="text-ink-secondary text-sm mt-1">{collection?.label}</p>
        </div>
        <div className="card p-10 flex flex-col items-center gap-3 text-center">
          <Bot className="w-10 h-10 text-warn opacity-60" />
          <p className="text-ink-primary font-medium">En desarrollo — Fase 4</p>
          <p className="text-ink-secondary text-sm max-w-sm">
            Scouting de equipos (export PDF) e informes individuales (export DOCX)
            con Gemini / OpenAI / Groq. Respuesta en streaming con vista previa en pantalla.
          </p>
        </div>
      </div>
    </PageTransition>
  )
}
