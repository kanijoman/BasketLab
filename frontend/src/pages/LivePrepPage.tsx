/**
 * LivePrepPage — Preparación live.
 * Genera el paquete de preparación (datos de temporada de un equipo y su rival) cifrado con una
 * contraseña, para importarlo en la app BasketLab Live. Solo competiciones FEB por ahora.
 */
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, Loader2, Radio } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, type TeamEntry } from '@/api/client'
import {
  downloadLivePackage, getLiveMatches, getLivePackageProgress, startLivePackage,
  type LiveMatch, type LivePackageProgress,
} from '@/api/livePackage'
import PageTransition from '@/components/ui/PageTransition'

const MIN_PASSPHRASE = 8

function formatStart(start: string | null): string {
  if (!start) return 'Fecha por confirmar'
  const d = new Date(start)
  return d.toLocaleString('es-ES', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}
type Phase = { kind: 'idle' } | { kind: 'running'; progress: LivePackageProgress | null } | { kind: 'done'; file: string } | { kind: 'error'; message: string }

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}

export default function LivePrepPage() {
  const { collection } = useCollection()
  const col = collection?.name ?? ''
  const [team, setTeam] = useState('')
  const [rival, setRival] = useState('')
  const [pass, setPass] = useState('')
  const [repeat, setRepeat] = useState('')
  const [matchCode, setMatchCode] = useState('')
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { data: teams = [] } = useQuery<TeamEntry[]>({
    queryKey: ['team-list', col],
    queryFn: () => getLiveTeamNames(col),
    enabled: Boolean(col) && !collection?.isFbcyl,
    staleTime: 10 * 60_000,
  })

  const { data: schedule } = useQuery({
    queryKey: ['live-matches', col, team],
    queryFn: () => getLiveMatches(col, team, 5),
    enabled: Boolean(col && team) && !collection?.isFbcyl,
    staleTime: 60_000,
    retry: false,
  })

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  function chooseMatch(m: LiveMatch) {
    setMatchCode(m.code)
    if (m.opponent) setRival(m.opponent.id)
  }

  function chooseRival(id: string) {
    setRival(id)
    const chosen = schedule?.matches.find(m => m.code === matchCode)
    if (chosen && chosen.opponent?.id !== id) setMatchCode('')
  }

  function chooseTeam(id: string) {
    setTeam(id)
    setMatchCode('')
  }

  const mismatch = repeat !== '' && pass !== repeat
  const shortPass = pass !== '' && pass.length < MIN_PASSPHRASE
  const sameTeam = team !== '' && team === rival
  const ready = Boolean(team && rival && !sameTeam && pass.length >= MIN_PASSPHRASE && pass === repeat)
  const running = phase.kind === 'running'

  async function poll(jobId: string) {
    try {
      const progress = await getLivePackageProgress(jobId)
      if (progress.status === 'error') {
        setPhase({ kind: 'error', message: progress.error ?? 'Error desconocido' })
        return
      }
      if (progress.status === 'done') {
        const blob = await downloadLivePackage(jobId)
        const name = `live_${progress.team}_vs_${progress.rival}.bpkg`.replace(/\s+/g, '_')
        saveBlob(blob, name)
        setPhase({ kind: 'done', file: name })
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
      const { job_id } = await startLivePackage({ collection: col, team_id: team, rival_id: rival, passphrase: pass, ...(matchCode ? { match_code: matchCode } : {}) })
      void poll(job_id)
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }

  const select = 'bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400'

  return (
    <PageTransition>
      <div className="space-y-4 max-w-2xl">
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">Preparación live</h1>
          <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
        </div>

        {!collection ? (
          <p className="text-sm text-ink-secondary">Selecciona una colección.</p>
        ) : collection.isFbcyl ? (
          <div className="card p-6 flex items-start gap-3">
            <Radio className="w-5 h-5 text-warn mt-0.5" />
            <p className="text-sm text-ink-secondary">
              Los paquetes de preparación live están disponibles solo para competiciones FEB por ahora.
            </p>
          </div>
        ) : (
          <div className="card p-5 space-y-4">
            <p className="text-sm text-ink-secondary">
              Genera un fichero cifrado con los datos de temporada de tu equipo y del rival para usarlo en la app
              BasketLab Live. Se procesan todos los partidos de la competición, puede tardar un poco.
            </p>
            <div className="grid sm:grid-cols-2 gap-4">
              <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                Equipo propio
                <select value={team} onChange={e => chooseTeam(e.target.value)} className={select} disabled={running}>
                  <option value="">— Selecciona —</option>
                  {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                Rival
                <select value={rival} onChange={e => chooseRival(e.target.value)} className={select} disabled={running}>
                  <option value="">— Selecciona —</option>
                  {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                Contraseña
                <input type="password" value={pass} onChange={e => setPass(e.target.value)} className={select}
                  autoComplete="new-password" disabled={running} />
              </label>
              <label className="flex flex-col gap-1 text-xs text-ink-secondary">
                Repetir contraseña
                <input type="password" value={repeat} onChange={e => setRepeat(e.target.value)} className={select}
                  autoComplete="new-password" disabled={running} />
              </label>
            </div>
            {team && schedule && (
              <fieldset className="space-y-2" disabled={running}>
                <legend className="text-xs text-ink-secondary">Próximos partidos de este equipo (opcional: fija el rival y el partido)</legend>
                {schedule.warning && <p className="text-xs text-warn">{schedule.warning}</p>}
                {schedule.matches.map(m => (
                  <label key={m.code} data-match className="flex items-center gap-2 text-sm text-ink-secondary cursor-pointer">
                    <input type="radio" name="live-match" checked={matchCode === m.code} onChange={() => chooseMatch(m)} />
                    <span>
                      {m.status === 'live' ? <strong className="text-up">En directo</strong> : formatStart(m.start)}
                      {' · '}{m.is_home ? 'vs' : '@'} <strong className="text-ink-primary">{m.opponent?.name.trim()}</strong>
                      {' '}(jornada {m.round})
                    </span>
                  </label>
                ))}
              </fieldset>
            )}
            {sameTeam && <p className="text-xs text-warn">El equipo propio y el rival deben ser distintos.</p>}
            {shortPass && <p className="text-xs text-warn">La contraseña debe tener al menos {MIN_PASSPHRASE} caracteres.</p>}
            {mismatch && <p className="text-xs text-warn">Las contraseñas no coinciden.</p>}

            <button className="btn-secondary" disabled={!ready || running} onClick={() => void generate()}>
              {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              Generar paquete
            </button>

            {phase.kind === 'running' && (
              <p className="text-sm text-ink-secondary">
                {phase.progress && phase.progress.total > 0
                  ? `Procesando… ${phase.progress.current} de ${phase.progress.total} partidos`
                  : 'Iniciando…'}
              </p>
            )}
            {phase.kind === 'error' && <p className="text-sm text-down">{phase.message}</p>}
            {phase.kind === 'done' && (
              <div className="text-sm text-ink-secondary space-y-1">
                <p className="text-up">Paquete descargado: {phase.file}</p>
                <p>Impórtalo en la app BasketLab Live con la misma contraseña.
                  <strong className="text-ink-primary"> Guarda la contraseña: no se puede recuperar.</strong></p>
              </div>
            )}
          </div>
        )}
      </div>
    </PageTransition>
  )
}
