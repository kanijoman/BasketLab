/**
 * BasketLab Live. The engine (Python in a Web Worker) works from a preparation package imported
 * from BasketLab ("Preparación live"). Without a package the demo replays a finished FEB game
 * second by second so alerts and substitution proposals can be seen working on the device. Real
 * feeds plug into the same EngineApi (issues #118/#119).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createWorkerEngine, type EngineApi } from '../engine/client'
import { loadDemoData, type DemoData } from '../engine/demo'
import type { Alert, EngineOutput, ReplayInfo, SessionMeta } from '../engine/types'
import { IndexedDbPackageStore, safeStore, type PackageStore } from '../package/storage'
import { summarizePackage, type PackageSummary } from '../package/summary'
import AlertCard, { clockLabel } from './AlertCard'
import PackagePanel from './PackagePanel'

interface Props {
  engine?: EngineApi
  loadDemo?: () => Promise<DemoData>
  store?: PackageStore
}

const SPEEDS = [1, 10, 30, 60]
type Phase = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready' }
interface Entry { alert: Alert; at: string }

export default function App({ engine: injected, loadDemo = loadDemoData, store: injectedStore }: Props) {
  const [engine] = useState<EngineApi>(() => injected ?? createWorkerEngine())
  const [store] = useState<PackageStore>(() => injectedStore ?? safeStore(new IndexedDbPackageStore()))
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [meta, setMeta] = useState<SessionMeta | null>(null)
  const [info, setInfo] = useState<ReplayInfo | null>(null)
  const [demo, setDemo] = useState<DemoData | null>(null)
  const [pkg, setPkg] = useState<PackageSummary | null>(null)
  const [out, setOut] = useState<EngineOutput | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  const [elapsed, setElapsed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [ms, setMs] = useState<number | null>(null)
  const busy = useRef(false)
  const elapsedRef = useRef(0)
  const seen = useRef(new Set<string>())

  const reset = useCallback(() => {
    seen.current.clear()
    elapsedRef.current = 0
    setEntries([]); setOut(null); setElapsed(0); setPlaying(false); setInfo(null)
  }, [])

  const beginDemo = useCallback(async (data: DemoData) => {
    setPhase({ kind: 'loading' })
    reset()
    setPkg(null)
    try {
      setMeta(await engine.start(data.package))
      setInfo(await engine.loadReplay(data.game))
      setPhase({ kind: 'ready' })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [engine, reset])

  const beginPackage = useCallback(async (plaintext: string) => {
    setPhase({ kind: 'loading' })
    reset()
    try {
      setMeta(await engine.start(plaintext))
      setPkg(summarizePackage(plaintext))
      setPhase({ kind: 'ready' })
    } catch (e) {
      setPkg(summarizePackage(plaintext))
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [engine, reset])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [data, saved] = await Promise.all([loadDemo(), store.load()])
        if (cancelled) return
        setDemo(data)
        if (saved) await beginPackage(saved.plaintext)
        else await beginDemo(data)
      } catch (e) {
        if (!cancelled) setPhase({ kind: 'error', message: String(e) })
      }
    })()
    return () => { cancelled = true }
  }, [loadDemo, store, beginDemo, beginPackage])

  useEffect(() => () => { if (!injected) engine.dispose() }, [engine, injected])

  const finished = info !== null && elapsed >= info.duration

  const step = useCallback(async (to: number) => {
    if (busy.current) return
    busy.current = true
    try {
      const t0 = performance.now()
      const result = await engine.replay(to)
      setMs(Math.round(performance.now() - t0))
      setOut(result)
      const at = clockLabel(result.snapshot.period, result.snapshot.remaining)
      const fresh = result.alerts.filter(a => !seen.current.has(a.key))
      fresh.forEach(a => seen.current.add(a.key))
      if (fresh.length) setEntries(prev => [...fresh.map(alert => ({ alert, at })), ...prev])
    } catch (e) {
      setPlaying(false)
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    } finally {
      busy.current = false
    }
  }, [engine])

  useEffect(() => {
    if (!playing || !info) return
    const timer = setInterval(() => {
      const next = Math.min(elapsedRef.current + speed, info.duration)
      elapsedRef.current = next
      setElapsed(next)
      void step(next)
      if (next >= info.duration) setPlaying(false)
    }, 1000)
    return () => clearInterval(timer)
  }, [playing, speed, info, step])

  const removePackage = useCallback(() => {
    setPkg(null)
    if (demo) void beginDemo(demo)
  }, [demo, beginDemo])

  const panel = (
    <PackagePanel engine={engine} store={store} loaded={pkg} onLoaded={s => { setPkg(s); void store.load().then(r => r && beginPackage(r.plaintext)) }}
      onRemoved={removePackage} />
  )

  if (phase.kind === 'loading') return <main className="screen"><p className="status">Cargando motor…</p></main>
  if (phase.kind === 'error') {
    return (
      <main className="screen">
        <p className="status error">No se pudo iniciar el motor</p>
        <p className="detail">{phase.message}</p>
        {pkg ? panel : demo && <button onClick={() => void beginDemo(demo)}>Reintentar</button>}
      </main>
    )
  }

  const own = meta!.team
  const rival = meta!.rival
  const snap = out?.snapshot
  return (
    <main className="screen">
      <header className="scoreboard">
        <div className="team"><span className="name">{own.name}</span><span className="pts">{snap?.score[own.id] ?? 0}</span></div>
        <div className="clock">{snap ? clockLabel(snap.period, snap.remaining) : 'Q1 10:00'}</div>
        <div className="team"><span className="name">{rival.name}</span><span className="pts">{snap?.score[rival.id] ?? 0}</span></div>
      </header>

      {pkg ? (
        <p className="status">Paquete cargado. La app queda a la espera del partido en directo (próximamente).</p>
      ) : (
        <>
          <section className="controls">
            <button onClick={() => setPlaying(p => !p)} disabled={finished}>{playing ? 'Pausa' : 'Reproducir'}</button>
            <label>
              Velocidad
              <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>
                {SPEEDS.map(s => <option key={s} value={s}>{s}×</option>)}
              </select>
            </label>
            <button className="secondary" onClick={() => demo && void beginDemo(demo)}>Reiniciar</button>
            {ms !== null && <span className="perf">{ms} ms</span>}
          </section>

          {finished && <p className="status">Partido finalizado</p>}

          <section>
            <h2>Alertas</h2>
            {entries.length === 0
              ? <p className="detail">Sin alertas todavía. Pulsa Reproducir para simular el partido.</p>
              : <ul className="alerts">{entries.map(e => <AlertCard key={e.alert.key} alert={e.alert} at={e.at} />)}</ul>}
          </section>
        </>
      )}

      {panel}
    </main>
  )
}
