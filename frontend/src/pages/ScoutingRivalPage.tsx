/**
 * ScoutingRivalPage — Scouting del rival.
 * Genera el informe de scouting (PDF) de CUALQUIER equipo de la competición a partir de sus partidos, evaluados con el motor
 * del directo, y lo muestra en pantalla antes de descargarlo. Trabajo previo semanal, solo en la web y solo FEB por ahora.
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, FileSearch, Loader2 } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, type TeamEntry } from '@/api/client'
import {
  downloadScoutingPdf, getScoutingProgress, getScoutingReport, startScouting,
  type ScoutingProgress, type ScoutingReport,
} from '@/api/scoutingRival'
import PageTransition from '@/components/ui/PageTransition'

type Phase =
  | { kind: 'idle' }
  | { kind: 'running'; progress: ScoutingProgress | null }
  | { kind: 'done'; jobId: string; report: ScoutingReport }
  | { kind: 'error'; message: string }

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  // Releasing the URL right after the click cancels the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

const fmt = (n: number, digits = 1) => n.toFixed(digits).replace('.', ',')
const ADVANTAGE_CLASS = { own: 'text-up', rival: 'text-down', even: 'text-ink-secondary', neutral: 'text-ink-secondary' } as const

const delta = (v: number | null) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v)} %`)
/** Colour of a gap against the league: green when it favours the scouted team (more of its own, less conceded), red when not; small gaps are plain. */
const deltaClass = (v: number | null, goodHigh: boolean) =>
  v == null || Math.abs(v) < 10 ? 'text-ink-secondary' : (v > 0) === goodHigh ? 'text-up' : 'text-down'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-sm font-semibold text-ink-primary">{title}</h3>
      {children}
    </section>
  )
}

function Preview({ report, onPdf, downloading }: { report: ScoutingReport; onPdf: () => void; downloading: boolean }) {
  const { record } = report
  return (
    <div className="card p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-ink-primary">{report.team.name}</h2>
          <p className="text-xs text-ink-secondary">
            {report.sample_games} partidos analizados · balance {record.wins}-{record.losses} · {fmt(record.avg_for)} a favor, {fmt(record.avg_against)} en contra
          </p>
        </div>
        <button className="btn-secondary" onClick={onPdf} disabled={downloading}>
          {downloading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          Descargar PDF
        </button>
      </div>

      {report.notices.map(n => <p key={n} className="text-sm text-warn">{n}</p>)}

      {report.profile.length > 0 && (
        <Section title="Perfil">
          <ul className="text-sm text-ink-secondary list-disc pl-5">{report.profile.map(p => <li key={p}>{p}</li>)}</ul>
        </Section>
      )}
      {report.keys.length > 0 && (
        <Section title="Claves tácticas">
          <ul className="text-sm text-ink-secondary list-disc pl-5 space-y-0.5">{report.keys.map(k => <li key={k.text}>{k.text}</li>)}</ul>
        </Section>
      )}
      {(report.plan.neutralize.length > 0 || report.plan.exploit.length > 0) && (
        <Section title="Plan de partido">
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            {([['Peligros a neutralizar', report.plan.neutralize, 'text-down'], ['Debilidades a explotar', report.plan.exploit, 'text-up']] as const).map(([title, items, cls]) => (
              items.length > 0 && (
                <div key={title}>
                  <p className={`font-medium ${cls}`}>{title}</p>
                  <ul className="text-ink-secondary list-disc pl-5 space-y-0.5">{items.map(i => <li key={i.text}>{i.text}</li>)}</ul>
                </div>
              )
            ))}
          </div>
        </Section>
      )}
      {report.players.length > 0 && (
        <Section title={report.gender === 'F' ? 'Jugadoras clave' : 'Jugadores clave'}>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-secondary"><th>{report.gender === 'F' ? 'Jugadora' : 'Jugador'}</th><th className="text-right">PJ</th><th className="text-right">Pts/p</th><th className="text-right">% puntos</th><th className="text-right">Pts cierre</th></tr></thead>
            <tbody>
              {report.players.map(p => (
                <tr key={p.id} className="border-t border-surface-border text-ink-secondary">
                  <td className="py-1 text-ink-primary">{p.name}</td><td className="text-right">{p.games}</td>
                  <td className="text-right">{fmt(p.pts_per_game)}</td><td className="text-right">{Math.round(p.share * 100)} %</td><td className="text-right">{p.clutch.pts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      {(report.origin?.length ?? 0) > 0 && (
        <Section title="Origen de los puntos">
          <p className="text-xs text-ink-secondary">Por partido, frente a la liga (definición por posesión). «Concede» = lo que anotan sus rivales.</p>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-secondary"><th></th><th className="text-right">Propio</th><th className="text-right">Liga</th><th className="text-right">Dif.</th><th className="text-right">Concede</th><th className="text-right">Dif.</th></tr></thead>
            <tbody>
              {report.origin.map(r => (
                <tr key={r.key} className="border-t border-surface-border text-ink-secondary">
                  <td className="py-1 text-ink-primary">{r.label}</td>
                  <td className="text-right">{r.own == null ? '—' : fmt(r.own)}</td>
                  <td className="text-right">{r.league == null ? '—' : fmt(r.league)}</td>
                  <td className={`text-right ${deltaClass(r.own_delta_pct, true)}`}>{delta(r.own_delta_pct)}</td>
                  <td className="text-right">{r.conceded == null ? '—' : fmt(r.conceded)}</td>
                  <td className={`text-right ${deltaClass(r.conceded_delta_pct, false)}`}>{delta(r.conceded_delta_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      {report.alerts.length > 0 && (
        <Section title="Alertas del motor sobre este equipo">
          <ul className="text-sm text-ink-secondary list-disc pl-5">{report.alerts.map(a => <li key={a.id}>{a.text}</li>)}</ul>
        </Section>
      )}
      {report.comparison.length > 0 && (
        <Section title={`Comparativa: ${report.own_team?.name ?? 'nuestro equipo'} frente a ${report.team.name}`}>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-secondary"><th>Estadística</th><th className="text-right">Propio</th><th className="text-right">Rival</th></tr></thead>
            <tbody>
              {report.comparison.filter(c => c.advantage !== 'neutral').slice(0, 14).map(c => (
                <tr key={c.key} className="border-t border-surface-border">
                  <td className="py-1 text-ink-primary">{c.label}</td>
                  <td className={`text-right ${c.advantage === 'own' ? ADVANTAGE_CLASS.own : 'text-ink-secondary'}`}>{c.own_text}</td>
                  <td className={`text-right ${c.advantage === 'rival' ? ADVANTAGE_CLASS.rival : 'text-ink-secondary'}`}>{c.rival_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      <p className="text-xs text-ink-secondary">El PDF incluye además las zonas de tiro, los quintetos, los cuartos y la lista de partidos.</p>
    </div>
  )
}

export default function ScoutingRivalPage() {
  const { collection } = useCollection()
  const col = collection?.name ?? ''
  const [rival, setRival] = useState('')
  const [own, setOwn] = useState('')
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const [downloading, setDownloading] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: teams = [] } = useQuery<TeamEntry[]>({
    queryKey: ['team-list', col],
    queryFn: () => getLiveTeamNames(col),
    enabled: Boolean(col) && !collection?.isFbcyl,
    staleTime: 10 * 60_000,
  })

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  const sameTeam = rival !== '' && rival === own
  const ready = Boolean(rival) && !sameTeam
  const running = phase.kind === 'running'

  async function poll(jobId: string) {
    try {
      const progress = await getScoutingProgress(jobId)
      if (progress.status === 'error') {
        setPhase({ kind: 'error', message: progress.error ?? 'Error desconocido' })
        return
      }
      if (progress.status === 'done') {
        setPhase({ kind: 'done', jobId, report: await getScoutingReport(jobId) })
        return
      }
      setPhase({ kind: 'running', progress })
      timer.current = setTimeout(() => void poll(jobId), 1000)
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }

  async function generate() {
    setPhase({ kind: 'running', progress: null })
    try {
      const { job_id } = await startScouting({ collection: col, team_id: rival, ...(own ? { own_team_id: own } : {}) })
      void poll(job_id)
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }

  async function downloadPdf(jobId: string, team: string) {
    setDownloading(true)
    try {
      saveBlob(await downloadScoutingPdf(jobId), `Scouting_${team.replace(/\W+/g, '_')}.pdf`)
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    } finally {
      setDownloading(false)
    }
  }

  const select = 'bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400'

  return (
    <PageTransition>
      <div className="space-y-4 max-w-3xl">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Scouting del rival</h1>
          <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
        </div>

        {!collection ? (
          <p className="text-sm text-ink-secondary">Selecciona una colección.</p>
        ) : collection.isFbcyl ? (
          <div className="card p-6 flex items-start gap-3">
            <FileSearch className="w-5 h-5 text-warn mt-0.5" />
            <p className="text-sm text-ink-secondary">El scouting del rival está disponible solo para competiciones FEB por ahora.</p>
          </div>
        ) : (
          <>
            <div className="card p-5 space-y-4">
              <p className="text-sm text-ink-secondary">
                Elige el equipo a analizar (cualquiera de la competición): se reproducen sus partidos como en directo con el motor
                y se genera un informe con sus claves tácticas, jugadores, quintetos, zonas y plan de partido. Puede tardar un poco.
              </p>
              <div className="grid sm:grid-cols-2 gap-4">
                <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                  Equipo a analizar
                  <select value={rival} onChange={e => setRival(e.target.value)} className={select} disabled={running}>
                    <option value="">— Selecciona —</option>
                    {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                  Nuestro equipo (opcional, para la comparativa)
                  <select value={own} onChange={e => setOwn(e.target.value)} className={select} disabled={running}>
                    <option value="">— Sin comparativa —</option>
                    {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </label>
              </div>
              {sameTeam && <p className="text-xs text-warn">El equipo a analizar y el nuestro deben ser distintos.</p>}
              <button className="btn-secondary" disabled={!ready || running} onClick={() => void generate()}>
                {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSearch className="w-3.5 h-3.5" />}
                Generar informe
              </button>

              {phase.kind === 'running' && (
                <div className="space-y-1">
                  <p className="text-sm text-ink-secondary">
                    {phase.progress && phase.progress.total > 0
                      ? `Procesando… ${phase.progress.current} de ${phase.progress.total} partidos`
                      : 'Iniciando…'}
                  </p>
                  {phase.progress && phase.progress.total > 0 && (
                    <div role="progressbar" aria-label="Progreso del informe" aria-valuemin={0}
                      aria-valuenow={phase.progress.current} aria-valuemax={phase.progress.total}
                      className="h-2 rounded-full bg-surface-border overflow-hidden">
                      <div className="h-full bg-accent-400 transition-all"
                        style={{ width: `${Math.round((phase.progress.current / phase.progress.total) * 100)}%` }} />
                    </div>
                  )}
                </div>
              )}
              {phase.kind === 'error' && <p className="text-sm text-down">{phase.message}</p>}
            </div>

            {phase.kind === 'done' && (
              <Preview report={phase.report} downloading={downloading} onPdf={() => void downloadPdf(phase.jobId, phase.report.team.name)} />
            )}
          </>
        )}
      </div>
    </PageTransition>
  )
}
