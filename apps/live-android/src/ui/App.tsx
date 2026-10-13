/**
 * BasketLab Live. The engine (Python in a Web Worker) works from a preparation package imported
 * from BasketLab ("Preparación live"). Without a package the demo replays a finished FEB game
 * second by second so alerts and substitution proposals can be seen working on the device. Real
 * feeds plug into the same EngineApi (issues #118/#119).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createWorkerEngine, type EngineApi } from '../engine/client'
import { loadDemoData, loadRealDemo as fetchRealDemo, type DemoData, type RealDemoData } from '../engine/demo'
import type { Alert, EngineOutput, RecordingFrame, ReplayInfo, SessionMeta } from '../engine/types'
import type { Fetcher } from '../package/remote'
import { IndexedDbPackageStore, safeStore, type PackageStore } from '../package/storage'
import { summarizePackage, type PackageSummary } from '../package/summary'
import AlertCard, { clockLabel } from './AlertCard'
import DemoControls, { type DemoSource } from './DemoControls'
import LiveConnect from './LiveConnect'
import { useLiveFeed, type FeedTiming } from '../feed/useLiveFeed'
import type { HttpGet } from '../feed/febClient'
import PaceCard from './PaceCard'
import PackagePanel from './PackagePanel'
import RemotePackages from './RemotePackages'

interface Props {
  engine?: EngineApi
  loadDemo?: () => Promise<DemoData>
  /** The real recorded match of the demo (injected in tests). */
  loadRealDemo?: () => Promise<RealDemoData>
  /** Network access to FEB for the live mode (native HTTP on the tablet; injected in tests). */
  febHttp?: HttpGet
  /** Polling timing of the live mode (defaults: 10 s; injected in tests). */
  feedTiming?: FeedTiming
  store?: PackageStore
  /** Network access of the published-packages list (injected in tests). */
  remoteFetcher?: Fetcher
}

type Phase = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready' }
interface Entry { alert: Alert; at: string }

export default function App({ engine: injected, loadDemo = loadDemoData, loadRealDemo = fetchRealDemo, store: injectedStore, remoteFetcher, febHttp, feedTiming }: Props) {
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
  const [source, setSource] = useState<DemoSource>('sample')
  const [feed, setFeed] = useState<RecordingFrame['feed']>('ok')
  const [notice, setNotice] = useState<string | null>(null)
  const [ms, setMs] = useState<number | null>(null)
  const busy = useRef(false)
  const elapsedRef = useRef(0)
  const seen = useRef(new Set<string>())

  const reset = useCallback(() => {
    seen.current.clear()
    elapsedRef.current = 0
    setEntries([]); setOut(null); setElapsed(0); setPlaying(false); setInfo(null); setFeed('ok'); setNotice(null)
  }, [])

  const beginDemo = useCallback(async (data: DemoData) => {
    setPhase({ kind: 'loading' })
    reset()
    setPkg(null)
    try {
      setMeta(await engine.start(data.package))
      setInfo(await engine.loadReplay(data.game))
      setSource('sample')
      setPhase({ kind: 'ready' })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [engine, reset])

  /** The real recorded match: the engine is fed with what FEB served (404 windows included). */
  const beginReal = useCallback(async (fallback: DemoData) => {
    setPhase({ kind: 'loading' })
    reset()
    setPkg(null)
    try {
      const real = await loadRealDemo()
      setMeta(await engine.start(real.package))
      setInfo(await engine.loadRecording(real.recording))
      setSource('real')
      setPhase({ kind: 'ready' })
    } catch (e) {
      await beginDemo(fallback)
      setNotice(`No se pudo cargar el partido real: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [engine, reset, loadRealDemo, beginDemo])

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

  /** What the screen shows for an engine output: the snapshot and the alerts not seen before. */
  const handleOutput = useCallback((result: EngineOutput) => {
    setOut(result)
    const at = clockLabel(result.snapshot.period, result.snapshot.remaining)
    const fresh = result.alerts.filter(a => !seen.current.has(a.key))
    fresh.forEach(a => seen.current.add(a.key))
    if (fresh.length) setEntries(prev => [...fresh.map(alert => ({ alert, at })), ...prev])
  }, [])

  const restartLive = useCallback(async () => {
    seen.current.clear()
    setEntries([]); setOut(null)
    const saved = await store.load()
    if (saved) setMeta(await engine.start(saved.plaintext))
  }, [engine, store])
  const live = useLiveFeed({ engine, http: febHttp, timing: feedTiming, onOutput: handleOutput, restart: restartLive })

  const step = useCallback(async (to: number) => {
    if (busy.current) return
    busy.current = true
    try {
      const t0 = performance.now()
      let result: EngineOutput | null
      if (source === 'real') {
        const frame = await engine.playRecording(to)
        setFeed(frame.feed)
        result = frame.output
      } else {
        result = await engine.replay(to)
      }
      setMs(Math.round(performance.now() - t0))
      if (!result) return // the feed answered nothing: the last state stays
      handleOutput(result)
    } catch (e) {
      setPlaying(false)
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    } finally {
      busy.current = false
    }
  }, [engine, source, handleOutput])

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

  const onLoaded = (s: PackageSummary) => { setPkg(s); void store.load().then(r => r && beginPackage(r.plaintext)) }
  const panel = (
    <>
      <RemotePackages engine={engine} store={store} onLoaded={onLoaded} fetcher={remoteFetcher} />
      <PackagePanel engine={engine} store={store} loaded={pkg} onLoaded={onLoaded} onRemoved={removePackage} />
    </>
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

      <PaceCard pace={out?.analysis?.pace} own={own} rival={rival} />

      {pkg ? (
        <LiveConnect matchCode={pkg.match?.code ?? null} state={live.state} running={live.running}
          onStart={code => void live.connect(code)} onStop={live.disconnect} />
      ) : (
        <>
          <DemoControls
            source={source} onSource={s => demo && void (s === 'real' ? beginReal(demo) : beginDemo(demo))}
            playing={playing} onPlay={() => setPlaying(p => !p)} finished={finished}
            speed={speed} onSpeed={setSpeed} onRestart={() => demo && void (source === 'real' ? beginReal(demo) : beginDemo(demo))}
            ms={ms} feed={feed} elapsed={elapsed} duration={info?.duration ?? null}
          />
          {notice && <p role="alert" className="status error">{notice}</p>}

          {finished && <p className="status">Partido finalizado</p>}
        </>
      )}

      <section>
        <h2>Alertas</h2>
        {entries.length === 0
          ? <p className="detail">{pkg ? 'Sin alertas todavía.' : 'Sin alertas todavía. Pulsa Reproducir para simular el partido.'}</p>
          : <ul className="alerts">{entries.map(e => <AlertCard key={e.alert.key} alert={e.alert} at={e.at} />)}</ul>}
      </section>

      {panel}
    </main>
  )
}
