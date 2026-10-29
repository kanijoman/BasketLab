/**
 * ReportPage — Informe Semanal
 * Informe semanal (ZIP de PNGs) y scouting individual del equipo (DOCX).
 * Stats de temporada → TeamStatsPage
 */
import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Download, CalendarDays, ClipboardList } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getLiveTeamNames,
  postWeeklyReport,
  getWeeklyReportProgress,
  downloadWeeklyReport,
  downloadIndividualScoutingDocx,
  type WeeklyReportProgress,
  type TeamEntry,
} from '@/api/client'
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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [scoutTeam,    setScoutTeam]    = useState('')
  const [scoutLoading, setScoutLoading] = useState(false)
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
                    setWeeklyProgress({ status: 'running', step: 0, total: 5, message: 'Iniciando…', error: null })
                    try {
                      const { job_id } = await postWeeklyReport(col, weeklyTeamA, weeklyTeamB)
                      await new Promise<void>((resolve, reject) => {
                        pollRef.current = setInterval(async () => {
                          try {
                            const prog = await getWeeklyReportProgress(job_id)
                            setWeeklyProgress(prog)
                            if (prog.status === 'done') {
                              clearInterval(pollRef.current!)
                              resolve()
                            } else if (prog.status === 'error') {
                              clearInterval(pollRef.current!)
                              reject(new Error(prog.error ?? 'Error desconocido'))
                            }
                          } catch (e) {
                            clearInterval(pollRef.current!)
                            reject(e)
                          }
                        }, 1500)
                      })
                      const blob = await downloadWeeklyReport(job_id)
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `informe_${col.slice(0, 20)}.zip`
                      a.click()
                      URL.revokeObjectURL(url)
                    } catch (err) {
                      console.error('Weekly report error:', err)
                    } finally {
                      setWeeklyLoading(false)
                    }
                  }}
                  className="w-full justify-center"
                >
                  {weeklyLoading ? 'Generando informe…' : 'Descargar ZIP'}
                </Button>
                {weeklyLoading && weeklyProgress && (
                  <div className="flex flex-col gap-1">
                    <div className="w-full h-1.5 rounded-full bg-surface-raised overflow-hidden">
                      <div
                        className="h-full bg-secondary transition-all duration-500"
                        style={{ width: `${weeklyProgress.total > 0 ? (weeklyProgress.step / weeklyProgress.total) * 100 : 0}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-ink-muted text-center">
                      {weeklyProgress.message}
                      {weeklyProgress.total > 0 && ` (${weeklyProgress.step}/${weeklyProgress.total})`}
                    </p>
                    {weeklyProgress.status === 'error' && (
                      <p className="text-xs text-warn text-center">{weeklyProgress.error}</p>
                    )}
                  </div>
                )}
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
                    try {
                      const blob = await downloadIndividualScoutingDocx(col, scoutTeam)
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `scouting_${scoutTeam}.docx`
                      a.click()
                      URL.revokeObjectURL(url)
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
              </div>
            </ReportCard>
          </div>
        )}
      </div>
    </PageTransition>
  )
}
