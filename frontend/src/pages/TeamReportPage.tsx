/**
 * TeamReportPage — informe automático por reglas del análisis propio.
 * Sustituye al antiguo análisis con IA: mismas secciones, generadas por reglas.
 *
 * Issues #627 y #635: el scouting de un rival tiene su página completa («Scouting del rival», en FEB y en FBCYL). Aquí solo queda el análisis propio y un
 * enlace a ella.
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
import EmptyState from '@/components/ui/EmptyState'
import TeamReportView from '@/components/TeamReportView'
import AccessPanel from '@/components/AccessPanel'

const MODE: ReportMode = 'own'

export default function TeamReportPage() {
  const { collection } = useCollection()
  const [teamId, setTeamId] = useState('')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)
  const col = collection?.name ?? ''
  const mode = MODE            // the rival scouting is the page «Scouting del rival» (#627, #635): this one is the own team's, in FEB and in FBCYL

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
      const label = 'Analisis'
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
              <Button variant="secondary" className="ml-auto" disabled={!report} loading={pdfLoading} onClick={handlePdf} icon={FileDown}>PDF</Button>
            </div>

            <p className="flex items-center gap-2 text-sm text-ink-muted">
              <FileSearch className="h-4 w-4 shrink-0 text-accent-text" aria-hidden="true" />
              <span>
                Para preparar a un rival usa{' '}
                <Link to={`/${encodeURIComponent(collection.name)}/scouting-rival`} className="font-medium text-accent-text hover:underline">Scouting del rival</Link>
                : el informe completo, con claves, plan, jugadoras y comparativa con tu equipo.
              </span>
            </p>

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
