/**
 * BasketLab Live. The engine (Python in a Web Worker) works from a preparation package imported
 * from BasketLab ("Preparación live"). Without a package the demo replays a finished FEB game
 * second by second so alerts and substitution proposals can be seen working on the device. Real
 * feeds plug into the same EngineApi (issues #118/#119).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createWorkerEngine, type EngineApi } from '../engine/client'
import {
  loadDemoData, loadManifest as fetchManifest, loadMatch as fetchMatch,
  type DemoData, type DemoMatch, type RealDemoData,
} from '../engine/demo'
import type { EngineOutput, RecordingFrame, ReplayInfo, SessionMeta } from '../engine/types'
import type { Fetcher } from '../package/remote'
import { IndexedDbPackageStore, safeStore, type PackageStore } from '../package/storage'
import { summarizePackage, type PackageSummary } from '../package/summary'
import { clockLabel } from './AlertCard'
import AlertList, { type AlertEntry } from './AlertList'
import DemoControls, { SAMPLE, type DemoSource, type SourceOption } from './DemoControls'
import Scoreboard from './Scoreboard'
import LiveConnect from './LiveConnect'
import { useLiveFeed, type FeedTiming } from '../feed/useLiveFeed'
import type { HttpGet } from '../feed/febClient'
import PaceCard from './PaceCard'
import FormationStatus from './FormationStatus'
import AboutPanel, { UpdateBanner, buildDiagnostics } from './AboutPanel'
import { useAppUpdate, type AppUpdateDeps } from '../about/useAppUpdate'
import PackagesTab from './PackagesTab'
import TabBar from './TabBar'
import { useTab } from './useTab'
import FeedbackPanel from './FeedbackPanel'
import { useFeedback } from '../feedback/useFeedback'

export type { AppUpdateDeps }

interface Props {
  engine?: EngineApi
  loadDemo?: () => Promise<DemoData>
  /** Recorded matches the demo can replay, newest first (injected in tests). */
  loadManifest?: () => Promise<DemoMatch[]>
  /** The package and the recording of one of them (injected in tests). */
  loadMatch?: (match: DemoMatch) => Promise<RealDemoData>
  /** Network access to FEB for the live mode (native HTTP on the tablet; injected in tests). */
  febHttp?: HttpGet
  /** Polling timing of the live mode (defaults: 10 s; injected in tests). */
  feedTiming?: FeedTiming
  store?: PackageStore
  /** Network access of the published-packages list (injected in tests). */
  remoteFetcher?: Fetcher
  /** Version and update check (injected in tests; the defaults use the app's own plugins and GitHub). */
  appUpdate?: AppUpdateDeps
}

type Phase = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready' }
type Entry = AlertEntry

export default function App({ engine: injected, loadDemo = loadDemoData, loadManifest = fetchManifest, loadMatch = fetchMatch, store: injectedStore, remoteFetcher, febHttp, feedTiming, appUpdate }: Props) {
  const [engine] = useState<EngineApi>(() => injected ?? createWorkerEngine())
  const [store] = useState<PackageStore>(() => injectedStore ?? safeStore(new IndexedDbPackageStore()))
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [meta, setMeta] = useState<SessionMeta | null>(null)
  const [info, setInfo] = useState<ReplayInfo | null>(null)
  const [demo, setDemo] = useState<DemoData | null>(null)
  const [matches, setMatches] = useState<DemoMatch[]>([])
  const [pkg, setPkg] = useState<PackageSummary | null>(null)
  const [out, setOut] = useState<EngineOutput | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  const [elapsed, setElapsed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [source, setSource] = useState<DemoSource>(SAMPLE)
  const [feed, setFeed] = useState<RecordingFrame['feed']>('ok')
  const [notice, setNotice] = useState<string | null>(null)
  const [ms, setMs] = useState<number | null>(null)
  const [tab, setTab] = useTab()
  const busy = useRef(false)
  const elapsedRef = useRef(0)
  const seen = useRef(new Set<string>())
  // the staff's answers belong to the match being followed: the package's match, else the demo being replayed
  const feedback = useFeedback(pkg ? `live:${pkg.match?.code ?? meta?.package_id ?? 'paquete'}` : `demo:${source}`, meta?.package_id ?? null)
  const { register: registerAlert } = feedback

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
      setSource(SAMPLE)
      setPhase({ kind: 'ready' })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [engine, reset])

  /** A recorded match: the engine is fed with what FEB served (404 windows included). */
  const beginRecorded = useCallback(async (match: DemoMatch, fallback: DemoData) => {
    setPhase({ kind: 'loading' })
    reset()
    setPkg(null)
    try {
      const real = await loadMatch(match)
      setMeta(await engine.start(real.package))
      setInfo(await engine.loadRecording(real.recording))
      setSource(match.code)
      setPhase({ kind: 'ready' })
    } catch (e) {
      await beginDemo(fallback)
      setNotice(`No se pudo cargar el partido ${match.title}: ${e instanceof Error ? e.message : String(e)}`)
    }
  }, [engine, reset, loadMatch, beginDemo])

  /** The default demo: the latest recorded match; the sample game when there are no recordings. */
  const beginDefault = useCallback(async (data: DemoData, recorded: DemoMatch[]) => {
    if (recorded.length) await beginRecorded(recorded[0], data)
    else await beginDemo(data)
  }, [beginRecorded, beginDemo])

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
        const [data, recorded, saved] = await Promise.all([loadDemo(), loadManifest().catch(() => [] as DemoMatch[]), store.load()])
        if (cancelled) return
        setDemo(data)
        setMatches(recorded)
        if (saved) await beginPackage(saved.plaintext)
        else await beginDefault(data, recorded)
      } catch (e) {
        if (!cancelled) setPhase({ kind: 'error', message: String(e) })
      }
    })()
    return () => { cancelled = true }
  }, [loadDemo, loadManifest, store, beginDefault, beginPackage])

  useEffect(() => () => { if (!injected) engine.dispose() }, [engine, injected])

  const finished = info !== null && elapsed >= info.duration

  /** What the screen shows for an engine output: the snapshot and the alerts not seen before. */
  const handleOutput = useCallback((result: EngineOutput) => {
    setOut(result)
    const at = clockLabel(result.snapshot.period, result.snapshot.remaining)
    const fresh = result.alerts.filter(a => !seen.current.has(a.key))
    fresh.forEach(a => { seen.current.add(a.key); registerAlert(a, result.snapshot.elapsed) })
    if (fresh.length) setEntries(prev => [...fresh.map(alert => ({ alert, at })), ...prev])
  }, [registerAlert])

  const restartLive = useCallback(async () => {
    seen.current.clear()
    setEntries([]); setOut(null)
    const saved = await store.load()
    if (saved) setMeta(await engine.start(saved.plaintext))
  }, [engine, store])
  const live = useLiveFeed({ engine, http: febHttp, timing: feedTiming, onOutput: handleOutput, restart: restartLive })
  const update = useAppUpdate(appUpdate)

  const step = useCallback(async (to: number) => {
    if (busy.current) return
    busy.current = true
    try {
      const t0 = performance.now()
      let result: EngineOutput | null
      if (source !== SAMPLE) {
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
    if (demo) void beginDefault(demo, matches)
  }, [demo, matches, beginDefault])

  const onLoaded = (s: PackageSummary) => { setPkg(s); void store.load().then(r => r && beginPackage(r.plaintext)) }
  const panel = <PackagesTab engine={engine} store={store} loaded={pkg} onLoaded={onLoaded} onRemoved={removePackage} fetcher={remoteFetcher} />

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
  const sources: SourceOption[] = [...matches.map(m => ({ value: m.code, label: m.title })), { value: SAMPLE, label: 'Partido de ejemplo' }]
  const pickSource = (value: DemoSource) => {
    const match = matches.find(m => m.code === value)
    if (demo) void (match ? beginRecorded(match, demo) : beginDemo(demo))
  }
  /** The timeline: forward jumps straight there; going back rebuilds the engine from the start (the alerts in between are not replayed). */
  const seek = async (to: number) => {
    setPlaying(false)
    if (to < elapsedRef.current && demo) {
      const match = matches.find(m => m.code === source)
      await (match ? beginRecorded(match, demo) : beginDemo(demo))
    }
    elapsedRef.current = to
    setElapsed(to)
    await step(to)
  }
  const homeFirst = (snap?.home_id ?? meta?.home_id) === rival.id
  const [home, away] = homeFirst ? [rival, own] : [own, rival]
  const matchTab = (
    <>
      {!pkg && (
        <p className="notice">
          Estás viendo un partido de demostración. Para seguir un partido real, carga un paquete de preparación en la pestaña Paquetes.{' '}
          <button className="secondary link-button" onClick={() => setTab('paquetes')}>Ir a Paquetes</button>
        </p>
      )}
      <Scoreboard own={own} rival={rival} homeId={snap?.home_id ?? meta?.home_id} score={snap?.score}
        clock={snap ? clockLabel(snap.period, snap.remaining) : 'Q1 10:00'} />

      <FormationStatus formation={out?.analysis?.formation} />

      <PaceCard pace={out?.analysis?.pace} own={own} rival={rival} />

      {pkg ? (
        <LiveConnect matchCode={pkg.match?.code ?? null} state={live.state} running={live.running}
          onStart={code => void live.connect(code)} onStop={live.disconnect} />
      ) : (
        <>
          <DemoControls
            source={source} sources={sources} onSource={pickSource}
            playing={playing} onPlay={() => setPlaying(p => !p)} finished={finished}
            speed={speed} onSpeed={setSpeed} onRestart={() => pickSource(source)} onSeek={to => void seek(to)}
            ms={ms} feed={feed} elapsed={elapsed} duration={info?.duration ?? null} home={home} away={away}
          />
          {notice && <p role="alert" className="status error">{notice}</p>}

          {finished && <p className="status">Partido finalizado</p>}
        </>
      )}

      <section>
        <h2>Alertas</h2>
        {entries.length === 0
          ? <p className="detail">{pkg ? 'Sin alertas todavía.' : 'Sin alertas todavía. Pulsa Reproducir para simular el partido.'}</p>
          : <AlertList entries={entries} verdicts={feedback.verdicts} onVerdict={feedback.setVerdict} />}
      </section>

      {feedback.records.length > 0 && (
        <FeedbackPanel records={feedback.records} exportJson={feedback.exportJson} fileName={feedback.fileName()} onClear={feedback.clear} />
      )}

    </>
  )
  const aboutTab = (
    <AboutPanel version={update.installed} update={update.result} checking={update.checking} onCheck={update.checkNow}
      onOpen={update.open} diagnostics={buildDiagnostics({ version: update.installed, userAgent: navigator.userAgent,
        packageId: meta?.package_id ?? null, schemaVersion: meta?.schema_version ?? null, feed: live.state.kind })} />
  )
  return (
    <main className="screen with-tabs">
      {update.result?.status === 'available' && !live.running && <UpdateBanner latest={update.result.latest} onOpen={update.open} />}
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'partido' ? matchTab : tab === 'paquetes' ? panel : aboutTab}
      </div>
      <TabBar active={tab} onChange={setTab} />
    </main>
  )
}
