/**
 * TeamReportPage — informe automático por reglas (análisis propio / scouting rival).
 * Sustituye al antiguo análisis con IA: mismas secciones, generadas por reglas.
 *
 * Issue #627: el scouting de un rival tiene su página completa («Scouting del rival», solo FEB). Aquí, en FEB, solo queda el análisis propio y un
 * enlace a ella; el modo rival (la versión por reglas) se mantiene en FBCYL, donde aún no hay otra cosa.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList, FileDown, FileSearch, Loader2 } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import type { TeamEntry } from '@/api/client'
import { downloadTeamReportPdf, getReportTeams, getTeamReport, type ReportMode } from '@/api/teamReport'
import { ScopedAccessError } from '@live-package/crypto'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import { Field, Select } from '@/components/ui/Field'
import SegmentedControl from '@/components/ui/SegmentedControl'
import EmptyState from '@/components/ui/EmptyState'
import TeamReportView from '@/components/TeamReportView'
import AccessPanel from '@/components/AccessPanel'

const MODES: { key: ReportMode; label: string; desc: string }[] = [
  { key: 'own',   label: 'Propio equipo',  desc: 'Análisis de rendimiento propio' },
  { key: 'rival', label: 'Scouting rival', desc: 'Informe de análisis pre-partido' },
]

export default function TeamReportPage() {
  const { collection } = useCollection()
  const [teamId, setTeamId] = useState('')
  const [chosenMode, setMode] = useState<ReportMode>('own')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const col = collection?.name ?? ''
  // in FEB the rival scouting is the page «Scouting del rival»: this one is the own team's (#627); FBCYL keeps both modes
  const hasRivalMode = Boolean(collection?.isFbcyl)
  const mode: ReportMode = hasRivalMode ? chosenMode : 'own'

  const { data: teams = [] } = useQuery<TeamEntry[]>({
    queryKey: ['report-team-list', col],                       // not 'team-list': that key holds the API's list, this one may come from web-data (#605)
    queryFn: () => getReportTeams(col),
    enabled: Boolean(col),
    staleTime: 10 * 60_000,
  })

  const { data: report, isFetching, error, refetch } = useQuery({
    queryKey: ['team-report', col, teamId, mode],
    queryFn: () => getTeamReport(col, teamId, mode),
    enabled: Boolean(col && teamId),
    staleTime: 5 * 60_000,
    retry: (count, e) => !(e instanceof ScopedAccessError) && count < 1,           // no key: asking again does not help
  })
  const needsKey = error instanceof ScopedAccessError

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
        <PageHeader title="Informe de equipo" subtitle={collection?.label} />

        {!collection ? (
          <div className="card">
            <EmptyState icon={ClipboardList} title="Selecciona una colección para generar informes." />
          </div>
        ) : (
          <>
            <div className="card p-4 flex flex-wrap items-end gap-4">
              <Field label="Equipo" className="min-w-[14rem]">
                <Select value={teamId} onChange={e => setTeamId(e.target.value)}>
                  <option value="">— Selecciona equipo —</option>
                  {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </Select>
              </Field>
              {hasRivalMode && (
                <SegmentedControl label="Tipo de informe" size="md" value={mode} onChange={setMode}
                  options={MODES.map(m => ({ value: m.key, label: m.label }))} />
              )}
              <Button variant="secondary" className="ml-auto" disabled={!report} loading={pdfLoading} onClick={handlePdf} icon={FileDown}>PDF</Button>
            </div>

            {!hasRivalMode ? (
              <p className="flex items-center gap-2 text-sm text-ink-muted">
                <FileSearch className="h-4 w-4 shrink-0 text-accent-text" aria-hidden="true" />
                <span>
                  Para preparar a un rival usa{' '}
                  <Link to={`/${encodeURIComponent(collection.name)}/scouting-rival`} className="font-medium text-accent-text hover:underline">Scouting del rival</Link>
                  : el informe completo, con claves, plan, jugadoras y comparativa con tu equipo.
                </span>
              </p>
            ) : mode === 'rival' && (
              <p className="text-sm text-ink-muted">
                Es la versión por reglas del scouting. El informe completo de «Scouting del rival» todavía no está disponible para FBCYL.
              </p>
            )}

            {pdfError && <p className="text-sm text-bad">{pdfError}</p>}
            {isFetching && (
              <p className="text-sm text-ink-muted flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" /> Generando informe…
              </p>
            )}
            {needsKey && <AccessPanel onUnlocked={() => void refetch()} />}
            {error && !needsKey && <p className="text-sm text-bad">{(error as Error).message}</p>}
            {!teamId && <p className="text-sm text-ink-muted">Elige un equipo para generar el informe.</p>}
            {report && !isFetching && (
              <>
                <h2 className="text-lg font-semibold text-ink">
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
