/** React side of the live feed: owns the LiveFeed of the running connection and exposes its state. */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { capacitorDevice, type Device } from './device'
import { FbcylClient } from './fbcylClient'
import { FbcylFeed } from './fbcylFeed'
import { FebClient, defaultHttp, type HttpGet } from './febClient'
import { FeedLagMeter, lagNote, type LagInfo, type LagSummary } from './feedLag'
import { fbcylMatchId, sourceOf, type FeedSource } from './feedSource'
import { LiveFeed, type FeedState, type LiveFeedOptions } from './liveFeed'

export type FeedTiming = Pick<LiveFeedOptions, 'intervalMs' | 'waitingIntervalMs' | 'tailPolls' | 'sleep' | 'now'> & {
  /** FBCYL: how often the calendar is read while the match is on, to see whether it is over (default 1 min). */
  calendarEveryMs?: number
}

interface Options {
  engine: EngineApi
  http?: HttpGet
  /** The tablet (screen on, back to the foreground, network back); the Capacitor one unless a test gives its own. */
  device?: Device
  /** Notes the live mode wants in the session log (issue #309). */
  onNote?: (text: string) => void
  timing?: FeedTiming
  /** Called with the engine output of every document of the feed. */
  onOutput: (output: EngineOutput) => void
  /** Called before connecting: gives the engine a fresh session and clears what the screen shows. */
  restart: () => Promise<void>
  /** Called with the last merged FEB document (JSON text) so the match can be kept for a later review (issue #407): when it ends (``complete``), when the staff
   *  disconnects halfway and every few minutes while it is followed, so closing the app loses little (issue #556). */
  onFinished?: (lastDocument: string, code: string, complete: boolean) => void
  /** Called when the connection ends (the match is over, or the staff disconnects) with the recording the engine kept of the feed (issue #416). */
  onRecording?: (recording: { code: string; recording: unknown; complete: boolean }) => void
}

/** How often the match followed is kept on the device while it is on (issue #556). */
const KEEP_EVERY_MS = 180_000

const RUNNING = new Set<FeedState['kind']>(['connecting', 'waiting', 'live', 'gap'])

/** What a connection needs besides the code of the match. */
export interface ConnectOptions {
  /** FBCYL only: the group of the match in the calendar of the federation, where the feed finds the match when it is about to start (`match.fbcyl_group` of the package). */
  fbcylGroup?: string
}

export function useLiveFeed({ engine, http = defaultHttp, device = capacitorDevice, onNote, timing, onOutput, restart, onFinished, onRecording }: Options) {
  const [state, setState] = useState<FeedState>({ kind: 'idle' })
  /** The league of the match being followed: the messages say it (the staff must not read «FEB» on a match of FBCYL). */
  const [source, setSource] = useState<FeedSource>('FEB')
  /** Whether the screen is being kept on (null: no connection running). */
  const [awake, setAwake] = useState<boolean | null>(null)
  const feed = useRef<LiveFeed | FbcylFeed | null>(null)
  /** A FBCYL match: its FEB document is the engine's (the stream is not FEB-shaped), asked when it has to be kept. */
  const fbcylMatch = useRef(false)
  /** How late the data of FEB is, measured on this connection (issue #411). */
  const meter = useRef<FeedLagMeter | null>(null)
  const [lag, setLag] = useState<LagSummary | null>(null)
  const lastDocument = useRef<string | null>(null)
  /** The match being recorded, until its recording is handed over (so a disconnection after the end does not save it twice). */
  const recording = useRef<string | null>(null)
  /** When the document was last kept for review (clock of the connection). */
  const keptAt = useRef(0)

  /** The feed goes silent when stopped, so "disconnected" is reported here. */
  const keepRecording = useCallback(async (complete: boolean) => {
    const code = recording.current
    recording.current = null
    if (code === null) return
    const kept = await engine.recording()
    if (kept) onRecording?.({ code, recording: kept, complete })
  }, [engine, onRecording])

  /** The delay of the connection goes to the session log when it ends: it is what decides how often FEB is asked (issue #411). */
  const noteLag = useCallback(() => {
    const summary = meter.current?.summary()
    meter.current = null
    if (summary && summary.polls > 1 && !fbcylMatch.current) onNote?.(lagNote(summary))      // FBCYL gives nothing to measure the delay with: no note, and never one that says FEB
  }, [onNote])

  /** Keeps the match followed for a later review: FEB's document is the last one merged here, FBCYL's is the engine's (asked, so it is async). */
  const keepDocument = useCallback((code: string, complete: boolean, merged?: string) => {
    if (fbcylMatch.current) void engine.lastDocument().then(doc => { if (doc !== null) onFinished?.(doc, code, complete) })
    else if ((merged ?? lastDocument.current) !== null) onFinished?.((merged ?? lastDocument.current)!, code, complete)
  }, [engine, onFinished])

  const disconnect = useCallback(() => {
    feed.current?.stop()
    setState({ kind: 'stopped' })
    noteLag()
    if (recording.current !== null) keepDocument(recording.current, false)
    void keepRecording(false)
  }, [keepDocument, keepRecording, noteLag])

  const connect = useCallback(async (code: string, options: ConnectOptions = {}) => {
    feed.current?.stop()
    const league = sourceOf(code)
    setSource(league)
    fbcylMatch.current = league === 'FBCYL'
    if (league === 'FBCYL' && !options.fbcylGroup) {
      // a package from before the group travelled in it: nothing can find the match in the calendar
      setState({ kind: 'gap', lastOkAt: null, message: 'El paquete no trae el grupo de FBCYL del partido: vuelve a descargarlo desde Partidos' })
      return
    }
    setState({ kind: 'connecting' })
    await restart()
    lastDocument.current = null
    meter.current = new FeedLagMeter()
    setLag(null)
    const clock = timing?.now ?? Date.now
    const started = clock()
    keptAt.current = started
    const at = () => (clock() - started) / 1000          // seconds since the first poll: the time of the recording
    await engine.beginRecording(code, new Date(started).toISOString())
    recording.current = code
    const onState = (state: FeedState) => {
      setState(state)
      if (state.kind !== 'finished') return
      noteLag()
      keepDocument(code, true)
      void keepRecording(true)
    }
    const observe = (info: LagInfo) => {
      meter.current?.observe(info)
      if (meter.current) setLag(meter.current.summary())
    }
    const keepEvery = (merged?: string) => {
      if (clock() - keptAt.current < KEEP_EVERY_MS) return
      keptAt.current = clock()
      keepDocument(code, false, merged)
    }
    const next = league === 'FBCYL'
      ? new FbcylFeed({
        ...timing, client: new FbcylClient(http), matchId: fbcylMatchId(code)!, groupId: options.fbcylGroup!, onState,
        onFailure: () => void engine.recordGap('stream', at()),
        onStream: async (body, info) => {
          observe(info)
          const reading = await engine.updateStreaming(body, at())
          if ('stale' in reading) return                      // the service answered a reading that goes backwards: nothing to show
          keepEvery()
          onOutput(reading)
        },
        onFinal: async (moves, stats) => { onOutput(await engine.updateFbcylFinal(moves, stats, at())) },
      })
      : new LiveFeed({
        ...timing, client: new FebClient(http), code, onState,
        onFailure: endpoint => void engine.recordGap(endpoint, at()),
        onDocument: async (json, info) => {
          lastDocument.current = json
          keepEvery(json)
          observe(info)
          onOutput(await engine.update(json, at()))
        },
      })
    feed.current = next
    void next.start()
  }, [engine, http, timing, onOutput, restart, keepDocument, keepRecording, noteLag])

  useEffect(() => () => feed.current?.stop(), [])

  const running = RUNNING.has(state.kind)
  // While connected (issues #219, #220): the screen stays on, and coming back to the foreground or getting the network back
  // polls FEB at once instead of waiting for the frozen timer.
  useEffect(() => {
    if (!running) return
    let cancelled = false
    void device.keepAwake().then(ok => { if (!cancelled) setAwake(ok) })
    const stopListening = device.onResume(reason => {
      feed.current?.poke()
      onNote?.(reason === 'foreground' ? `La app vuelve a primer plano: se consulta ${source} de inmediato` : `Red recuperada: se consulta ${source} de inmediato`)
    })
    return () => { cancelled = true; stopListening(); setAwake(null); void device.allowSleep() }
  }, [running, device, onNote, source])

  return { state, running, awake, lag, source, connect, disconnect }
}
