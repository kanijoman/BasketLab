/**
 * ReportPage — Informe Semanal
 * Informe semanal (ZIP de PNGs) y scouting individual del equipo (DOCX).
 * Stats de temporada → TeamStatsPage
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Download, CalendarDays, ClipboardList } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, type TeamEntry } from '@/api/client'
import ProgressBar from '@/components/ui/ProgressBar'
import { downloadIndividualScoutingDocx, type DocxProgress } from '@/api/individualScouting'
import { downloadWeeklyReport, type WeeklyReportProgress } from '@/api/weeklyReport'
import { saveBlob } from '@/lib/download'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import { Field, Select } from '@/components/ui/Field'

// ---------------------------------------------------------------------------

interface ReportCardProps {
  icon: React.ReactNode
  title: string
  description: string
  badge: string
  children: React.ReactNode
}

function ReportCard({ icon, title, description, badge, children }: ReportCardProps) {
  return (
    <div className="card p-5 flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-secondary/10 text-secondary-text">{icon}</div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-ink">{title}</h3>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-raised text-ink-muted">{badge}</span>
          </div>
          <p className="text-xs text-ink-muted mt-0.5">{description}</p>
        </div>
      </div>
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------

export default function ReportPage() {
  const { collection } = useCollection()

  const [weeklyTeamA,   setWeeklyTeamA]   = useState('')
  const [weeklyTeamB,   setWeeklyTeamB]   = useState('')
  const [weeklyLoading, setWeeklyLoading] = useState(false)
  const [weeklyProgress, setWeeklyProgress] = useState<WeeklyReportProgress | null>(null)
  const [weeklyError,   setWeeklyError]   = useState<string | null>(null)
  const [scoutTeam,    setScoutTeam]    = useState('')
  const [scoutLoading, setScoutLoading] = useState(false)
  const [scoutProgress, setScoutProgress] = useState<DocxProgress | null>(null)
  const [scoutError,   setScoutError]   = useState<string | null>(null)

  const { data: teams = [] } = useQuery<TeamEntry[]>({
    queryKey: ['team-list', collection?.name],
    queryFn:  () => getLiveTeamNames(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 10 * 60_000,
  })

  const col = collection?.name ?? ''

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <PageHeader title="Informes" subtitle={collection?.label} />

        {!collection && (
          <div className="card p-10 flex flex-col items-center gap-2 text-center">
            <FileText className="w-8 h-8 text-warn opacity-40" />
            <p className="text-ink-muted text-sm">Selecciona una colección para generar informes.</p>
          </div>
        )}

        {collection && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {/* Weekly report ZIP */}
            <ReportCard
              icon={<CalendarDays className="w-5 h-5" />}
              title="Informe Semanal"
              description="Bundle completo de PNG: estadísticas generales, comparativas, último partido, stats individuales y gráficos de lanzamiento para dos equipos."
              badge="ZIP"
            >
              <div className="flex flex-col gap-2">
                <Field label="Equipo propio (A)">
                  <Select value={weeklyTeamA} onChange={e => setWeeklyTeamA(e.target.value)}
                    options={[{ value: '', label: '— Equipo propio (A) —' }, ...teams.map(t => ({ value: t.id, label: t.name }))]} />
                </Field>
                <Field label="Equipo rival (B)">
                  <Select value={weeklyTeamB} onChange={e => setWeeklyTeamB(e.target.value)}
                    options={[{ value: '', label: '— Equipo rival (B) —' }, ...teams.map(t => ({ value: t.id, label: t.name }))]} />
                </Field>
                {weeklyTeamA && weeklyTeamB && weeklyTeamA === weeklyTeamB && (
                  <p className="text-xs text-warn">Los equipos A y B deben ser diferentes.</p>
                )}
                <Button
                  variant="secondary"
                  icon={Download}
                  loading={weeklyLoading}
                  disabled={!weeklyTeamA || !weeklyTeamB || weeklyTeamA === weeklyTeamB}
                  onClick={async () => {
                    setWeeklyLoading(true)
                    setWeeklyError(null)
                    setWeeklyProgress({ status: 'running', step: 0, total: 5, message: 'Iniciando…', error: null })
                    try {
                      saveBlob(await downloadWeeklyReport(col, weeklyTeamA, weeklyTeamB, setWeeklyProgress), `informe_${col.slice(0, 20)}.zip`)
                    } catch (err) {
                      setWeeklyError(err instanceof Error ? err.message : 'Error generando el informe')
                    } finally {
                      setWeeklyLoading(false)
                    }
                  }}
                  className="w-full justify-center"
                >
                  {weeklyLoading ? 'Generando informe…' : 'Descargar ZIP'}
                </Button>
                {weeklyError && <p className="text-xs text-warn">{weeklyError}</p>}
                {weeklyLoading && weeklyProgress && <ProgressBar step={weeklyProgress.step} total={weeklyProgress.total} message={weeklyProgress.message} />}
              </div>
            </ReportCard>

            {/* Individual scouting DOCX */}
            <ReportCard
              icon={<ClipboardList className="w-5 h-5" />}
              title="Scouting Individual"
              description="Una página por jugador del equipo: identidad, estadísticas, perfil de tiro y radar, con espacio para las notas del cuerpo técnico."
              badge="DOCX"
            >
              <div className="flex flex-col gap-2">
                <Field label="Equipo a analizar">
                  <Select value={scoutTeam} onChange={e => setScoutTeam(e.target.value)}
                    options={[{ value: '', label: '— Equipo —' }, ...teams.map(t => ({ value: t.id, label: t.name }))]} />
                </Field>
                <Button
                  variant="secondary"
                  icon={Download}
                  loading={scoutLoading}
                  disabled={!scoutTeam}
                  onClick={async () => {
                    setScoutLoading(true)
                    setScoutError(null)
                    setScoutProgress(null)
                    try {
                      const blob = await downloadIndividualScoutingDocx(col, scoutTeam, setScoutProgress)
                      saveBlob(blob, `scouting_${scoutTeam}.docx`)
                    } catch (err) {
                      setScoutError(err instanceof Error ? err.message : 'Error descargando el DOCX')
                    } finally {
                      setScoutLoading(false)
                    }
                  }}
                  className="w-full justify-center"
                >
                  {scoutLoading ? 'Generando documento…' : 'Descargar DOCX'}
                </Button>
                {scoutError && <p className="text-xs text-warn">{scoutError}</p>}
                {scoutLoading && scoutProgress && (
                  <ProgressBar step={scoutProgress.current} total={scoutProgress.total}
                    message={scoutProgress.stage === 'charts' ? 'Gráficos de los jugadores' : 'Montando el documento'} />
                )}
              </div>
            </ReportCard>
          </div>
        )}
      </div>
    </PageTransition>
  )
}
