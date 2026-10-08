/**
 * TeamReportPage — informe automático por reglas (análisis propio / scouting rival).
 * Sustituye al antiguo análisis con IA: mismas secciones, generadas por reglas.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList, FileDown, Loader2 } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, type TeamEntry } from '@/api/client'
import { downloadTeamReportPdf, getTeamReport, type ReportMode } from '@/api/teamReport'
import PageTransition from '@/components/ui/PageTransition'
import TeamReportView from '@/components/TeamReportView'

const MODES: { key: ReportMode; label: string; desc: string }[] = [
  { key: 'own',   label: 'Propio equipo',  desc: 'Análisis de rendimiento propio' },
  { key: 'rival', label: 'Scouting rival', desc: 'Informe de análisis pre-partido' },
]

export default function TeamReportPage() {
  const { collection } = useCollection()
  const [teamId, setTeamId] = useState('')
  const [mode, setMode] = useState<ReportMode>('own')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const col = collection?.name ?? ''

  const { data: teams = [] } = useQuery<TeamEntry[]>({
    queryKey: ['team-list', col],
    queryFn: () => getLiveTeamNames(col),
    enabled: Boolean(col),
    staleTime: 10 * 60_000,
  })

  const { data: report, isFetching, error } = useQuery({
    queryKey: ['team-report', col, teamId, mode],
    queryFn: () => getTeamReport(col, teamId, mode),
    enabled: Boolean(col && teamId),
    staleTime: 5 * 60_000,
  })

  async function handlePdf() {
    setPdfLoading(true)
    setPdfError(null)
    try {
      const blob = await downloadTeamReportPdf(col, teamId, mode)
      const label = mode === 'rival' ? 'Scouting' : 'Analisis'
      const name = (report?.team ?? 'equipo').replace(/\s+/g, '_')
      const a = Object.assign(document.createElement('a'), {
        href: URL.createObjectURL(blob), download: `${label}_${name}.pdf`,
      })
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (e) {
      setPdfError(e instanceof Error ? e.message : 'Error generando PDF')
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <PageTransition>
      <div className="space-y-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Informe de equipo</h1>
          <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
        </div>

        {!collection ? (
          <div className="card p-10 flex flex-col items-center gap-2 text-center">
            <ClipboardList className="w-8 h-8 text-warn opacity-40" />
            <p className="text-ink-secondary text-sm">Selecciona una colección para generar informes.</p>
          </div>
        ) : (
          <>
            <div className="card p-4 flex flex-wrap items-end gap-4">
              <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                Equipo
                <select
                  value={teamId}
                  onChange={e => setTeamId(e.target.value)}
                  className="bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
                >
                  <option value="">— Selecciona equipo —</option>
                  {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              <div className="flex gap-4">
                {MODES.map(m => (
                  <label key={m.key} className="flex items-center gap-2 text-sm cursor-pointer" title={m.desc}>
                    <input type="radio" name="report-mode" value={m.key} checked={mode === m.key}
                      onChange={() => setMode(m.key)} />
                    {m.label}
                  </label>
                ))}
              </div>
              <button className="btn-secondary ml-auto" disabled={!report || pdfLoading} onClick={handlePdf}>
                {pdfLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />}
                PDF
              </button>
            </div>

            {pdfError && <p className="text-sm text-down">{pdfError}</p>}
            {isFetching && (
              <p className="text-sm text-ink-secondary flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Generando informe…
              </p>
            )}
            {error && <p className="text-sm text-down">{(error as Error).message}</p>}
            {!teamId && <p className="text-sm text-ink-secondary">Elige un equipo para generar el informe.</p>}
            {report && !isFetching && (
              <>
                <h2 className="text-lg font-semibold text-ink-primary">
                  {mode === 'rival' ? 'Scouting rival' : 'Análisis de equipo'}: {report.team}
                </h2>
                <TeamReportView report={report} />
              </>
            )}
          </>
        )}
      </div>
    </PageTransition>
  )
}
