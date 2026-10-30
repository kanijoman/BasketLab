/**
 * ScoutingRivalPage — Scouting del rival.
 * Genera el informe de scouting (PDF) de CUALQUIER equipo de la competición a partir de sus partidos, evaluados con el motor
 * del directo, y lo muestra en pantalla antes de descargarlo. Trabajo previo semanal, solo en la web y solo FEB por ahora.
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, FileSearch } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, type TeamEntry } from '@/api/client'
import {
  downloadScoutingPdf, getPublishedScouting, getScoutingProgress, getScoutingReport, getScoutingScopes, startScouting,
  type ScoutingProgress, type ScoutingReport, type ScoutingScope,
} from '@/api/scoutingRival'
import { ScopedAccessError } from '@live-package/crypto'
import AccessPanel from '@/components/AccessPanel'
import PageTransition from '@/components/ui/PageTransition'
import { saveBlob } from '@/lib/download'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import { Field, Select } from '@/components/ui/Field'
import SegmentedControl from '@/components/ui/SegmentedControl'

type Phase =
  | { kind: 'idle' }
  | { kind: 'running'; progress: ScoutingProgress | null }
  | { kind: 'done'; jobId: string | null; report: ScoutingReport }      // `jobId` null: the report was published (no PDF to download from a job)
  | { kind: 'locked' }                                                   // published, sealed, and this browser has no key for it
  | { kind: 'error'; message: string }

const SCOPE_LABEL: Record<ScoutingScope, string> = { liga: 'Liga', copa: 'Copa', todo: 'Agrupado' }

const fmt = (n: number, digits = 1) => n.toFixed(digits).replace('.', ',')
const ADVANTAGE_CLASS = { own: 'text-ok', rival: 'text-bad', even: 'text-ink-muted', neutral: 'text-ink-muted' } as const

const delta = (v: number | null) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v)} %`)
/** Colour of a gap against the league: green when it favours the scouted team (more of its own, less conceded), red when not; small gaps are plain. */
const deltaClass = (v: number | null, goodHigh: boolean) =>
  v == null || Math.abs(v) < 10 ? 'text-ink-muted' : (v > 0) === goodHigh ? 'text-ok' : 'text-bad'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {children}
    </section>
  )
}

function Preview({ report, onPdf, downloading }: { report: ScoutingReport; onPdf?: () => void; downloading: boolean }) {
  const { record } = report
  return (
    <div className="card p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-ink">{report.team.name}</h2>
          <p className="text-xs text-ink-muted">
            {report.sample_games} partidos analizados · balance {record.wins}-{record.losses} · {fmt(record.avg_for)} a favor, {fmt(record.avg_against)} en contra
          </p>
        </div>
        {onPdf && (
          <Button variant="secondary" icon={Download} loading={downloading} onClick={onPdf}>Descargar PDF</Button>
        )}
      </div>

      {report.notices.map(n => <p key={n} className="text-sm text-warn">{n}</p>)}

      {report.profile.length > 0 && (
        <Section title="Perfil">
          <ul className="text-sm text-ink-muted list-disc pl-5">{report.profile.map(p => <li key={p}>{p}</li>)}</ul>
        </Section>
      )}
      {report.keys.length > 0 && (
        <Section title="Claves tácticas">
          <ul className="text-sm text-ink-muted list-disc pl-5 space-y-0.5">{report.keys.map(k => <li key={k.text}>{k.text}</li>)}</ul>
        </Section>
      )}
      {(report.plan.neutralize.length > 0 || report.plan.exploit.length > 0) && (
        <Section title="Plan de partido">
          <div className="grid sm:grid-cols-2 gap-4 text-sm">
            {([['Peligros a neutralizar', report.plan.neutralize, 'text-bad'], ['Debilidades a explotar', report.plan.exploit, 'text-ok']] as const).map(([title, items, cls]) => (
              items.length > 0 && (
                <div key={title}>
                  <p className={`font-medium ${cls}`}>{title}</p>
                  <ul className="text-ink-muted list-disc pl-5 space-y-0.5">{items.map(i => <li key={i.text}>{i.text}</li>)}</ul>
                </div>
              )
            ))}
          </div>
        </Section>
      )}
      {report.players.length > 0 && (
        <Section title={report.gender === 'F' ? 'Jugadoras clave' : 'Jugadores clave'}>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-muted"><th>{report.gender === 'F' ? 'Jugadora' : 'Jugador'}</th><th className="text-right">PJ</th><th className="text-right">Pts/p</th><th className="text-right">% puntos</th><th className="text-right">Pts cierre</th></tr></thead>
            <tbody>
              {report.players.map(p => (
                <tr key={p.id} className="border-t border-line text-ink-muted">
                  <td className="py-1 text-ink">{p.name}</td><td className="text-right">{p.games}</td>
                  <td className="text-right">{fmt(p.pts_per_game)}</td><td className="text-right">{Math.round(p.share * 100)} %</td><td className="text-right">{p.clutch.pts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      {(report.origin?.length ?? 0) > 0 && (
        <Section title="Origen de los puntos">
          <p className="text-xs text-ink-muted">Por partido, frente a la liga (definición por posesión). «Concede» = lo que anotan sus rivales.</p>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-muted"><th></th><th className="text-right">Propio</th><th className="text-right">Liga</th><th className="text-right">Dif.</th><th className="text-right">Concede</th><th className="text-right">Dif.</th></tr></thead>
            <tbody>
              {report.origin.map(r => (
                <tr key={r.key} className="border-t border-line text-ink-muted">
                  <td className="py-1 text-ink">{r.label}</td>
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
          <ul className="text-sm text-ink-muted list-disc pl-5">{report.alerts.map(a => <li key={a.id}>{a.text}</li>)}</ul>
        </Section>
      )}
      {report.comparison.length > 0 && (
        <Section title={`Comparativa: ${report.own_team?.name ?? 'nuestro equipo'} frente a ${report.team.name}`}>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-ink-muted"><th>Estadística</th><th className="text-right">Propio</th><th className="text-right">Rival</th></tr></thead>
            <tbody>
              {report.comparison.filter(c => c.advantage !== 'neutral').slice(0, 14).map(c => (
                <tr key={c.key} className="border-t border-line">
                  <td className="py-1 text-ink">{c.label}</td>
                  <td className={`text-right ${c.advantage === 'own' ? ADVANTAGE_CLASS.own : 'text-ink-muted'}`}>{c.own_text}</td>
                  <td className={`text-right ${c.advantage === 'rival' ? ADVANTAGE_CLASS.rival : 'text-ink-muted'}`}>{c.rival_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}
      <p className="text-xs text-ink-muted">El PDF incluye además las zonas de tiro, los quintetos, los cuartos y la lista de partidos.</p>
    </div>
  )
}

export default function ScoutingRivalPage() {
  const { collection } = useCollection()
  const col = collection?.name ?? ''
  const [rival, setRival] = useState('')
  const [own, setOwn] = useState('')
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const [scopes, setScopes] = useState<ScoutingScope[]>([])          // what is published for the rival chosen (none: the report is generated)
  const [scope, setScope] = useState<ScoutingScope>('liga')
  const [scopesOf, setScopesOf] = useState('')                          // the rival the scopes above belong to: until it is the chosen one, nothing is known yet
  const [downloading, setDownloading] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: teams = [] } = useQuery<TeamEntry[]>({
    queryKey: ['team-list', col],
    queryFn: () => getLiveTeamNames(col),
    enabled: Boolean(col) && !collection?.isFbcyl,
    staleTime: 10 * 60_000,
  })

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  // What is published for the rival (issue #638): Liga, Copa or both. Without it (dataset off, nothing published, no cup games) the page works as always.
  useEffect(() => {
    let current = true
    setScopes([])
    setScope('liga')
    const known = (found: ScoutingScope[]) => { if (current) { setScopes(found); setScopesOf(rival) } }
    if (col && rival) getScoutingScopes(col, rival).then(known, () => known([]))
    return () => { current = false }
  }, [col, rival])

  const sameTeam = rival !== '' && rival === own
  const ready = Boolean(rival) && !sameTeam && scopesOf === rival                // it waits to know whether the scouting is published (instant when it is off)
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

  // Published scouting has no matchup (it depends on a pair of teams): with «Nuestro equipo» chosen the report is generated as always.
  const published = scopes.length > 0 && !own

  async function generate(chosen: ScoutingScope = scope) {
    setPhase({ kind: 'running', progress: null })
    try {
      if (published) {
        const report = await getPublishedScouting(col, rival, chosen)
        if (report) {
          setPhase({ kind: 'done', jobId: null, report })
          return
        }
      }
      const { job_id } = await startScouting({ collection: col, team_id: rival, ...(own ? { own_team_id: own } : {}) })
      void poll(job_id)
    } catch (e) {
      if (e instanceof ScopedAccessError) setPhase({ kind: 'locked' })
      else setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
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

  return (
    <PageTransition>
      <div className="space-y-4 max-w-3xl">
        <PageHeader title="Scouting del rival" subtitle={collection?.label} />

        {!collection ? (
          <p className="text-sm text-ink-muted">Selecciona una colección.</p>
        ) : collection.isFbcyl ? (
          <div className="card p-6 flex items-start gap-3">
            <FileSearch className="w-5 h-5 text-warn mt-0.5" />
            <p className="text-sm text-ink-muted">El scouting del rival está disponible solo para competiciones FEB por ahora.</p>
          </div>
        ) : (
          <>
            <div className="card p-5 space-y-4">
              <p className="text-sm text-ink-muted">
                Elige el equipo a analizar (cualquiera de la competición): se reproducen sus partidos como en directo con el motor
                y se genera un informe con sus claves tácticas, jugadores, quintetos, zonas y plan de partido. Puede tardar un poco.
              </p>
              <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Equipo a analizar">
                  <Select value={rival} onChange={e => setRival(e.target.value)} disabled={running}>
                    <option value="">— Selecciona —</option>
                    {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </Select>
                </Field>
                <Field label="Nuestro equipo (opcional, para la comparativa)">
                  <Select value={own} onChange={e => setOwn(e.target.value)} disabled={running}>
                    <option value="">— Sin comparativa —</option>
                    {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </Select>
                </Field>
              </div>
              {sameTeam && <p className="text-xs text-warn">El equipo a analizar y el nuestro deben ser distintos.</p>}
              {scopes.length > 1 && !own && (
                <SegmentedControl label="Partidos a analizar" size="md" value={scope}
                  onChange={next => { if (running) return; setScope(next); if (phase.kind === 'done' && phase.jobId === null) void generate(next) }}
                  options={scopes.map(s => ({ value: s, label: SCOPE_LABEL[s] }))} />
              )}
              {scopes.length > 0 && own && (
                <p className="text-xs text-ink-muted">Con «Nuestro equipo» elegido el informe se genera en el servidor, con la comparativa.</p>
              )}
              <Button variant="secondary" icon={FileSearch} loading={running} disabled={!ready} onClick={() => void generate()}>
                Generar informe
              </Button>

              {phase.kind === 'running' && (
                <div className="space-y-1">
                  <p className="text-sm text-ink-muted">
                    {phase.progress && phase.progress.total > 0
                      ? `Procesando… ${phase.progress.current} de ${phase.progress.total} partidos`
                      : 'Iniciando…'}
                  </p>
                  {phase.progress && phase.progress.total > 0 && (
                    <div role="progressbar" aria-label="Progreso del informe" aria-valuemin={0}
                      aria-valuenow={phase.progress.current} aria-valuemax={phase.progress.total}
                      className="h-2 rounded-full bg-line overflow-hidden">
                      <div className="h-full bg-secondary-text transition-all"
                        style={{ width: `${Math.round((phase.progress.current / phase.progress.total) * 100)}%` }} />
                    </div>
                  )}
                </div>
              )}
              {phase.kind === 'error' && <p className="text-sm text-bad">{phase.message}</p>}
              {phase.kind === 'locked' && <AccessPanel onUnlocked={() => void generate()} />}
            </div>

            {phase.kind === 'done' && (
              <Preview report={phase.report} downloading={downloading}
                onPdf={phase.jobId ? () => void downloadPdf(phase.jobId as string, phase.report.team.name) : undefined} />
            )}
          </>
        )}
      </div>
    </PageTransition>
  )
}
