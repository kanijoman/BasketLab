/**
 * ReportPage — Informe Semanal
 * Scouting individual → AIAnalysisPage · Scouting rival → AIAnalysisPage
 * Stats de temporada → TeamStatsPage
 * Aquí: solo el informe semanal completo (ZIP de PNGs).
 */
import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Download, CalendarDays } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getPlayerStats,
  postWeeklyReport,
  getWeeklyReportProgress,
  downloadWeeklyReport,
  type PlayerStat,
  type WeeklyReportProgress,
} from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

// ---------------------------------------------------------------------------

function ChevronDownIcon() {
  return (
    <svg className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary"
      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  )
}

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
        <div className="p-2 rounded-lg bg-accent-500/10 text-accent-400">{icon}</div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-ink-primary">{title}</h3>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-hover text-ink-secondary">{badge}</span>
          </div>
          <p className="text-xs text-ink-secondary mt-0.5">{description}</p>
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

  const { data: players = [] } = useQuery<PlayerStat[]>({
    queryKey: ['player-list', collection?.name],
    queryFn:  () => getPlayerStats(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
    select: rows => [...rows].sort((a, b) => a.player_name.localeCompare(b.player_name)),
  })

  // Unique sorted team list from player stats
  const teams = [...new Set(players.map(p => p.team_name))].sort()

  const col = collection?.name ?? ''

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Informes</h1>
          <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
        </div>

        {!collection && (
          <div className="card p-10 flex flex-col items-center gap-2 text-center">
            <FileText className="w-8 h-8 text-warn opacity-40" />
            <p className="text-ink-secondary text-sm">Selecciona una colección para generar informes.</p>
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
                <div className="relative">
                  <select
                    value={weeklyTeamA}
                    onChange={e => setWeeklyTeamA(e.target.value)}
                    className="w-full appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-2 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
                  >
                    <option value="">— Equipo propio (A) —</option>
                    {teams.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <ChevronDownIcon />
                </div>
                <div className="relative">
                  <select
                    value={weeklyTeamB}
                    onChange={e => setWeeklyTeamB(e.target.value)}
                    className="w-full appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-2 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
                  >
                    <option value="">— Equipo rival (B) —</option>
                    {teams.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <ChevronDownIcon />
                </div>
                {weeklyTeamA && weeklyTeamB && weeklyTeamA === weeklyTeamB && (
                  <p className="text-xs text-warn">Los equipos A y B deben ser diferentes.</p>
                )}
                <button
                  disabled={
                    !weeklyTeamA ||
                    !weeklyTeamB ||
                    weeklyTeamA === weeklyTeamB ||
                    weeklyLoading
                  }
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
                  className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-accent-500 text-white text-sm font-medium hover:bg-accent-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Download className="w-4 h-4" />
                  {weeklyLoading ? 'Generando informe…' : 'Descargar ZIP'}
                </button>
                {weeklyLoading && weeklyProgress && (
                  <div className="flex flex-col gap-1">
                    <div className="w-full h-1.5 rounded-full bg-surface-hover overflow-hidden">
                      <div
                        className="h-full bg-accent-500 transition-all duration-500"
                        style={{ width: `${weeklyProgress.total > 0 ? (weeklyProgress.step / weeklyProgress.total) * 100 : 0}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-ink-secondary text-center">
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
          </div>
        )}
      </div>
    </PageTransition>
  )
}
