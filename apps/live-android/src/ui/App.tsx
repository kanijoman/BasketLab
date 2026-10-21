/**
 * BasketLab Live. The engine (Python in a Web Worker) works from a preparation package imported
 * from BasketLab ("Preparación live"). Without a package the demo replays a finished FEB game
 * second by second so alerts and substitution proposals can be seen working on the device. Real
 * feeds plug into the same EngineApi (issues #118/#119).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createWorkerEngine, type EngineApi } from '../engine/client'
import {
  demoLabel, loadDemoData, loadManifest as fetchManifest, loadMatch as fetchMatch, orderDemos,
  type DemoData, type DemoMatch, type RealDemoData,
} from '../engine/demo'
import type { EngineOutput, LoggedAlert, PostMatchReport, RecordingFrame, ReplayInfo, SessionMeta } from '../engine/types'
import { loadFavorites } from '../package/favorites'
import type { Fetcher } from '../package/remote'
import { IndexedDbPackageStore, safeStore, type PackageStore } from '../package/storage'
import { summarizePackage, type PackageSummary } from '../package/summary'
import { clockLabel } from './AlertCard'
import AlertList, { type AlertEntry } from './AlertList'
import { useAlertPacer } from './useAlertPacer'
import DemoControls, { SAMPLE, mmss, type DemoSource, type SourceOption } from './DemoControls'
import Scoreboard from './Scoreboard'
import LiveConnect from './LiveConnect'
import { useLiveFeed, type FeedTiming } from '../feed/useLiveFeed'
import type { HttpGet } from '../feed/febClient'
import type { Device } from '../feed/device'
import BrandHeader from './BrandHeader'
import PaceCard from './PaceCard'
import Splash from './Splash'
import WinProbCard from './WinProbCard'
import { useExperimental } from './useExperimental'
import { ALERT_MODES, useAlertMode, type AlertMode } from './useAlertMode'
import { useSessionLog } from './useSessionLog'
import { useWinProbHistory } from './useWinProbHistory'
import FormationStatus from './FormationStatus'
import FinishedMatches from './FinishedMatches'
import PackageMismatch from './PackageMismatch'
import RecordingsPanel from './RecordingsPanel'
import { IndexedDbRecordingStore, encodeRecording, safeRecordingStore, type RecordingStore, type SavedRecording } from '../feed/recordingStore'
import { reportBlocks } from '../postmatch/blocks'
import { fileNameFor, shareFile as shareFileDefault, sharePdf } from '../postmatch/share'
import { IndexedDbFinishedStore, safeFinishedStore, type FinishedMatch, type FinishedStore } from '../feed/finishedStore'
import AboutPanel, { UpdateBanner, VersionFooter, buildDiagnostics } from './AboutPanel'
import { useAppUpdate, type AppUpdateDeps } from '../about/useAppUpdate'
import PackagesTab from './PackagesTab'
import { listenInviteLinks } from '../package/inviteLink'
import ReviewSwitch from './ReviewSwitch'
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
  /** Screen on and back-to-foreground events of the tablet (injected in tests; the default uses the Capacitor plugins). */
  device?: Device
  store?: PackageStore
  /** Recordings of the live matches kept for sharing (injected in tests). */
  recordingStore?: RecordingStore
  /** Gives a file to the staff: the share sheet of the tablet, a download in a browser (injected in tests). */
  shareFile?: (bytes: Uint8Array, fileName: string, title: string, mime: string) => Promise<void>
  /** Draws and shares the post-match PDF (injected in tests; the defaults use jsPDF and the share sheet of the tablet). */
  pdf?: PdfDeps
  /** Finished live matches kept for a later review (injected in tests). */
  finishedStore?: FinishedStore
  /** Network access of the published-packages list (injected in tests). */
  remoteFetcher?: Fetcher
  /** Version and update check (injected in tests; the defaults use the app's own plugins and GitHub). */
  appUpdate?: AppUpdateDeps
  /** Time between two alerts of a burst of the live feed (issue #375; tests shorten it). */
  alertCooldownMs?: number
}

const FINISHED = 'finished:'
/** Whether the source is replayed from one final document (the sample game and the finished live matches) and not from a recording. */
const isReplayDoc = (source: DemoSource) => source === SAMPLE || source.startsWith(FINISHED)

export interface PdfDeps {
  render(report: PostMatchReport): Promise<Uint8Array>
  share(bytes: Uint8Array, fileName: string, title: string): Promise<void>
}
const defaultPdf: PdfDeps = {
  render: async report => (await import('../postmatch/pdf')).renderPdf(reportBlocks(report)),
  share: (bytes, fileName, title) => sharePdf(bytes, fileName, title),
}

type Phase = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready' }
type Entry = AlertEntry

export default function App({ engine: injected, loadDemo = loadDemoData, loadManifest = fetchManifest, loadMatch = fetchMatch, store: injectedStore, finishedStore: injectedFinished, recordingStore: injectedRecordings, shareFile = shareFileDefault, pdf = defaultPdf, remoteFetcher, febHttp, feedTiming, device, appUpdate, alertCooldownMs }: Props) {
  const [engine] = useState<EngineApi>(() => injected ?? createWorkerEngine())
  const [store] = useState<PackageStore>(() => injectedStore ?? safeStore(new IndexedDbPackageStore()))
  const [finishedStore] = useState<FinishedStore>(() => injectedFinished ?? safeFinishedStore(new IndexedDbFinishedStore()))
  const [finishedMatches, setFinishedMatches] = useState<FinishedMatch[]>([])
  const [recordingStore] = useState<RecordingStore>(() => injectedRecordings ?? safeRecordingStore(new IndexedDbRecordingStore()))
  const [recordings, setRecordings] = useState<SavedRecording[]>([])
  const [reporting, setReporting] = useState<string | null>(null)
  const [reportError, setReportError] = useState<string | null>(null)
  /** Every alert of the match being followed, with its clock label: the annex of the post-match report (issue #409). */
  const alertLog = useRef<LoggedAlert[]>([])
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })
  const [meta, setMeta] = useState<SessionMeta | null>(null)
  const [info, setInfo] = useState<ReplayInfo | null>(null)
  const [demo, setDemo] = useState<DemoData | null>(null)
  const [matches, setMatches] = useState<DemoMatch[]>([])
  const [pkg, setPkg] = useState<PackageSummary | null>(null)
  // reviewing a recorded match while the package stays saved (issue #344); the live view is a package that is not being reviewed
  const [reviewing, setReviewing] = useState(false)
  /** Moments of the recorded match in which something new appears (issue #345); empty for the sample game. */
  const [events, setEvents] = useState<number[]>([])
  const liveMode = pkg !== null && !reviewing
  const [out, setOut] = useState<EngineOutput | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  // the alerts of the live feed are presented one by one (issue #375); the rest (replays, jumps, a loaded match) all at once
  const pacer = useAlertPacer(useCallback((items: Entry[]) => setEntries(prev => [...items, ...prev]), []), alertCooldownMs)
  const [elapsed, setElapsed] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [source, setSource] = useState<DemoSource>(SAMPLE)
  const [feed, setFeed] = useState<RecordingFrame['feed']>('ok')
  const [notice, setNotice] = useState<string | null>(null)
  const [ms, setMs] = useState<number | null>(null)
  const [tab, setTab] = useTab()
  // an invitation link opened the app (issue #410): its right is kept, the list of matches is shown and says what happened
  const [inviteNotice, setInviteNotice] = useState<string | null>(null)
  useEffect(() => listenInviteLinks(result => {
    setInviteNotice(result.ok ? `Invitación aceptada: ${result.scope}.` : result.message)
    setTab('paquetes')
  }), [setTab])
  const [winProbOn, setWinProbOn] = useExperimental('win_prob')
  const winProbHistory = useWinProbHistory(out)
  const session = useSessionLog()
  // the engine hears the mode before the first package starts (the effects run in this order and the worker serves requests in order)
  const [alertMode, setAlertMode] = useAlertMode()
  useEffect(() => { void engine.setMode(alertMode) }, [engine, alertMode])
  const chooseAlertMode = useCallback((next: AlertMode) => {
    setAlertMode(next)
    session.record(`Modo de alertas: ${ALERT_MODES.find(m => m.id === next)?.label ?? next}`)
  }, [setAlertMode, session.record])  // eslint-disable-line react-hooks/exhaustive-deps
  const busy = useRef(false)
  const elapsedRef = useRef(0)
  const seen = useRef(new Set<string>())
  // the staff's answers belong to the match being followed: the package's match, else the demo being replayed
  const feedback = useFeedback(liveMode ? `live:${pkg!.match?.code ?? meta?.package_id ?? 'paquete'}` : `demo:${source}`, meta?.package_id ?? null, undefined, alertMode)
  const { register: registerAlert } = feedback

  const reset = useCallback(() => {
    seen.current.clear()
    alertLog.current = []
    pacer.clear()
    elapsedRef.current = 0
    setEntries([]); setOut(null); setElapsed(0); setPlaying(false); setInfo(null); setFeed('ok'); setNotice(null)
  }, [pacer])

  const beginDemo = useCallback(async (data: DemoData) => {
    setPhase({ kind: 'loading' })
    reset()
    setReviewing(true)
    try {
      setMeta(await engine.start(data.package))
      setInfo(await engine.loadReplay(data.game))
      setEvents([])
      setSource(SAMPLE)
      setPhase({ kind: 'ready' })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [engine, reset])

  /** A live match that ended and was kept (issue #407): its package and its last document replay like the sample game. */
  const beginFinished = useCallback(async (code: string) => {
    const saved = await finishedStore.load(code)
    if (!saved) { setNotice('No se encontró el partido guardado'); return }
    setPhase({ kind: 'loading' })
    reset()
    setReviewing(true)
    try {
      setMeta(await engine.start(saved.plaintext))
      setInfo(await engine.loadReplay(saved.game))
      setEvents([])
      setSource(`${FINISHED}${code}`)
      setPhase({ kind: 'ready' })
    } catch (e) {
      setPhase({ kind: 'error', message: e instanceof Error ? e.message : String(e) })
    }
  }, [engine, reset, finishedStore])

  /** Shares the file of a recording: the one the repository keeps in ``tests/recordings`` (issue #416). */
  const shareRecording = useCallback(async (code: string) => {
    const saved = await recordingStore.load(code)
    if (!saved) return
    const gz = saved.encoding === 'gzip'
    await shareFile(saved.bytes, `grabacion-${code}.rec.json${gz ? '.gz' : ''}`, `Grabación del partido ${saved.title}`, gz ? 'application/gzip' : 'application/json')
    session.record(`Grabación del partido ${code} compartida`)
  }, [recordingStore, shareFile, session.record])  // eslint-disable-line react-hooks/exhaustive-deps

  /** The post-match analysis of a kept match as a PDF the staff can share (issue #409). */
  const reportFinished = useCallback(async (code: string) => {
    setReporting(code)
    setReportError(null)
    try {
      const saved = await finishedStore.load(code)
      if (!saved) throw new Error('el partido ya no está guardado')
      const report = await engine.report(saved.game, saved.alerts ?? [], saved.ownId)
      const title = `Informe del partido ${report.match.own.name.trim()} – ${report.match.rival.name.trim()}`
      await pdf.share(await pdf.render(report), fileNameFor(report.match.own.name, report.match.rival.name, code), title)
      session.record(`Informe PDF del partido ${code}`)
    } catch (e) {
      setReportError(`No se pudo generar el informe: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setReporting(null)
    }
  }, [engine, finishedStore, pdf, session.record])  // eslint-disable-line react-hooks/exhaustive-deps

  /** A recorded match: the engine is fed with what FEB served (404 windows included). */
  const beginRecorded = useCallback(async (match: DemoMatch, fallback: DemoData) => {
    setPhase({ kind: 'loading' })
    reset()
    setReviewing(true)
    try {
      const real = await loadMatch(match)
      setMeta(await engine.start(real.package))
      const recording = await engine.loadRecording(real.recording)
      setInfo(recording)
      setEvents(recording.events ?? [])
      // start at the first event, not in the minutes before the match (issue #346); the timeline still shows the whole recording
      const start = recording.start_at ?? 0
      elapsedRef.current = start
      setElapsed(start)
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
    setReviewing(false)
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
  useEffect(() => { void finishedStore.list().then(setFinishedMatches) }, [finishedStore])
  useEffect(() => { void recordingStore.list().then(setRecordings) }, [recordingStore])

  const finished = info !== null && elapsed >= info.duration

  /** What the screen shows for an engine output: the snapshot and the alerts not seen before. */
  const handleOutput = useCallback((result: EngineOutput, paced = false) => {
    setOut(result)
    const at = clockLabel(result.snapshot.period, result.snapshot.remaining)
    const fresh = result.alerts.filter(a => !seen.current.has(a.key))
    fresh.forEach(a => { seen.current.add(a.key); registerAlert(a, result.snapshot.elapsed); alertLog.current.push({ alert: a, at }) })
    pacer.push(fresh, at, paced)
  }, [registerAlert, pacer])
  const handleLiveOutput = useCallback((result: EngineOutput) => handleOutput(result, true), [handleOutput])

  const restartLive = useCallback(async () => {
    seen.current.clear()
    alertLog.current = []
    pacer.clear()
    setEntries([]); setOut(null)
    const saved = await store.load()
    if (saved) setMeta(await engine.start(saved.plaintext))
  }, [engine, store, pacer])
  const metaRef = useRef<SessionMeta | null>(null)
  metaRef.current = meta
  /** The match ended: keep it on the device so it can be reviewed afterwards (issue #407). */
  const keepFinished = useCallback(async (game: string, code: string) => {
    const saved = await store.load()
    const current = metaRef.current
    if (!saved || !current) return
    const match: FinishedMatch = {
      code, title: `${current.team.name} – ${current.rival.name}`, savedAt: new Date().toISOString(), ownId: current.team.id,
      alerts: [...alertLog.current], plaintext: saved.plaintext, game,
    }
    await finishedStore.save(match)
    setFinishedMatches(await finishedStore.list())
    session.record(`Partido ${code} finalizado y guardado para revisarlo`)
  }, [store, finishedStore, session.record])  // eslint-disable-line react-hooks/exhaustive-deps
  /** The engine kept a recording of the feed (issue #416): it is saved, gzipped, whether the match ended or the staff disconnected. */
  const keepRecording = useCallback(async ({ code, recording, complete }: { code: string; recording: unknown; complete: boolean }) => {
    const current = metaRef.current
    const { encoding, bytes } = await encodeRecording(JSON.stringify(recording))
    await recordingStore.save({
      code, title: current ? `${current.team.name} – ${current.rival.name}` : code, savedAt: new Date().toISOString(), complete,
      frames: (recording as { frames?: unknown[] }).frames?.length ?? 0, encoding, bytes,
    })
    setRecordings(await recordingStore.list())
    session.record(`Grabación del partido ${code} guardada (${complete ? 'completa' : 'incompleta'})`)
  }, [recordingStore, session.record])  // eslint-disable-line react-hooks/exhaustive-deps
  const live = useLiveFeed({ engine, http: febHttp, device, onNote: session.record, timing: feedTiming, onOutput: handleLiveOutput, restart: restartLive,
    onFinished: keepFinished, onRecording: keepRecording })
  const update = useAppUpdate(appUpdate)

  const step = useCallback(async (to: number) => {
    if (busy.current) return
    busy.current = true
    try {
      const t0 = performance.now()
      let result: EngineOutput | null
      if (!isReplayDoc(source)) {
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

  const { record } = session
  const removePackage = useCallback(() => {
    record('Paquete quitado: vuelve la demostración')
    setPkg(null)
    setReviewing(false)
    if (demo) void beginDefault(demo, matches)
  }, [demo, matches, beginDefault, record])

  const reviewRecorded = () => {
    if (!demo) return
    record('Revisión de un partido grabado: el paquete sigue guardado')
    void beginDefault(demo, matches)
  }
  const backToPackage = () => {
    record('Vuelta al partido del paquete')
    void store.load().then(r => r && beginPackage(r.plaintext))
  }
  const onLoaded = (s: PackageSummary) => { record('Paquete cargado: el partido empieza de nuevo'); setPkg(s); void store.load().then(r => r && beginPackage(r.plaintext)) }
  const panel = <PackagesTab engine={engine} store={store} loaded={pkg} onLoaded={onLoaded} onRemoved={removePackage} fetcher={remoteFetcher} notice={inviteNotice} />

  if (phase.kind === 'loading') return <Splash />
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
  const current = source.startsWith(FINISHED) ? finishedMatches.find(m => `${FINISHED}${m.code}` === source) : undefined
  const favorites = loadFavorites()      // the demos of the teams of interest first (issue #441); read on each render: it is marked in another tab
  const sources: SourceOption[] = [...(current ? [{ value: source, label: current.title }] : []),
    ...orderDemos(matches, favorites).map(m => ({ value: m.code, label: demoLabel(m) })), { value: SAMPLE, label: 'Partido de ejemplo' }]
  const pickSource = (value: DemoSource) => {
    if (value.startsWith(FINISHED)) { void beginFinished(value.slice(FINISHED.length)); return }
    const match = matches.find(m => m.code === value)
    if (demo) void (match ? beginRecorded(match, demo) : beginDemo(demo))
  }
  /** The next moment with something new: nothing happens in between, so it needs no question and the alerts of the tramo are none (#345). */
  const nextEvent = events.find(t => t > elapsedRef.current + 0.5)
  const goToNextEvent = async () => {
    // a quick second tap waits for the engine to finish the first jump, so the screen never shows a time the engine has not reached
    while (busy.current) await new Promise<void>(resolve => setTimeout(resolve, 10))
    const to = events.find(t => t > elapsedRef.current + 0.5)
    if (to === undefined) return
    record('Salto al siguiente evento')
    elapsedRef.current = to
    setElapsed(to)
    await step(to)
  }
  /** The timeline: forward jumps straight there; going back rebuilds the engine from the start (the alerts in between are not replayed). */
  const seek = async (to: number) => {
    setPlaying(false)
    if (to < elapsedRef.current && demo) {
      const match = matches.find(m => m.code === source)
      if (source.startsWith(FINISHED)) await beginFinished(source.slice(FINISHED.length))
      else await (match ? beginRecorded(match, demo) : beginDemo(demo))
    }
    elapsedRef.current = to
    setElapsed(to)
    await step(to)
  }
  // the count is about the alerts of THIS run (#314): the history of earlier runs of the same match stays in the device, not in the count
  const shownKeys = new Set(entries.map(e => e.alert.key))
  const shownFeedback = feedback.records.filter(r => shownKeys.has(r.key))
  const homeFirst = (snap?.home_id ?? meta?.home_id) === rival.id
  const [home, away] = homeFirst ? [rival, own] : [own, rival]
  const matchTab = (
    <>
      {pkg && <ReviewSwitch reviewing={reviewing} disabled={live.running} onLive={backToPackage} onReview={reviewRecorded} />}
      <FinishedMatches matches={finishedMatches} disabled={live.running} onReview={code => { record(`Revisión del partido finalizado ${code}`); void beginFinished(code) }}
        onReport={code => void reportFinished(code)} reporting={reporting} error={reportError} />
      <RecordingsPanel recordings={recordings} onShare={code => void shareRecording(code)} />
      {!pkg && (
        <p className="notice">
          Estás viendo un partido de demostración. Para seguir un partido real, carga un paquete de preparación en la pestaña Partidos.{' '}
          <button className="secondary link-button" onClick={() => setTab('paquetes')}>Ir a Partidos</button>
        </p>
      )}
      {out?.package_match?.ok === false && (
        <PackageMismatch match={out.package_match.found.map(id => snap?.teams[id]?.name?.trim() ?? id)} own={own} rival={rival}
          onPackages={() => setTab('paquetes')} />
      )}
      <Scoreboard own={own} rival={rival} homeId={snap?.home_id ?? meta?.home_id} score={snap?.score}
        clock={snap ? clockLabel(snap.period, snap.remaining) : 'Q1 10:00'} />

      {/* the playback controls stay under the scoreboard to play comfortably (#405) */}
      {!liveMode && (
        <>
          <DemoControls
            source={source} sources={sources}
            onSource={value => { record(`Cambio de partido de la demostración (${value})`); pickSource(value) }}
            playing={playing} onPlay={() => setPlaying(p => !p)} finished={finished}
            speed={speed} onSpeed={setSpeed} onRestart={() => { record('Partido reiniciado con el botón Reiniciar'); pickSource(source) }}
            onSeek={to => { record(`Salto en la línea de tiempo a ${mmss(to)}`); void seek(to) }}
            onNextEvent={events.length ? () => void goToNextEvent() : undefined} hasNextEvent={nextEvent !== undefined}
            ms={ms} feed={feed} elapsed={elapsed} duration={info?.duration ?? null} home={home} away={away}
          />
          {notice && <p role="alert" className="status error">{notice}</p>}

          {finished && <p className="status">Partido finalizado</p>}
        </>
      )}

      {/* the order of the screen (#405): scoreboard, (playback controls), pace, win probability, alerts; the rest goes after them */}
      <PaceCard pace={out?.analysis?.pace} own={own} rival={rival} />
      {winProbOn && <WinProbCard winProb={out?.analysis?.win_prob} levers={out?.analysis?.win_levers} own={own} history={winProbHistory} />}

      <section>
        <h2>Alertas</h2>
        {entries.length === 0
          ? <p className="detail">{liveMode ? 'Sin alertas todavía.' : 'Sin alertas todavía. Pulsa Reproducir para simular el partido.'}</p>
          : <AlertList entries={entries} verdicts={feedback.verdicts} onVerdict={feedback.setVerdict}
              clock={snap ? { period: snap.period, remaining: snap.remaining } : undefined} />}
      </section>

      <FormationStatus formation={out?.analysis?.formation} own={own} rival={rival} />

      {liveMode && (
        <LiveConnect matchCode={pkg.match?.code ?? null} state={live.state} running={live.running} awake={live.awake} lag={live.lag}
          onStart={code => void live.connect(code)} onStop={live.disconnect} />
      )}

      {shownFeedback.length > 0 && (
        <FeedbackPanel records={shownFeedback} exportJson={feedback.exportJson} fileName={feedback.fileName()} onClear={feedback.clear} />
      )}

      <VersionFooter version={update.installed} engineVersion={meta?.engine_version ?? null} />
    </>
  )
  const aboutTab = (
    <AboutPanel version={update.installed} update={update.result} checking={update.checking} onCheck={update.checkNow}
      onOpen={update.open} diagnostics={buildDiagnostics({ version: update.installed, userAgent: navigator.userAgent,
        packageId: meta?.package_id ?? null, schemaVersion: meta?.schema_version ?? null, feed: live.state.kind,
        engineVersion: meta?.engine_version ?? null, sessionLog: session.lines })} sessionLog={session.lines} engineVersion={meta?.engine_version ?? null} schemaVersion={meta?.schema_version ?? null}
      experimental={{ winProb: winProbOn, onWinProb: setWinProbOn }} alertMode={{ mode: alertMode, onMode: chooseAlertMode }} />
  )
  return (
    <main className="screen with-tabs">
      <BrandHeader />
      {update.result?.status === 'available' && !live.running && <UpdateBanner latest={update.result.latest} onOpen={update.open} />}
      <div role="tabpanel" key={tab} className="tab-fade" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'partido' ? matchTab : tab === 'paquetes' ? panel : aboutTab}
      </div>
      <TabBar active={tab} onChange={setTab} />
    </main>
  )
}
