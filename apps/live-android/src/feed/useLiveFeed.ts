/** React side of the live feed: owns the LiveFeed of the running connection and exposes its state. */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { capacitorDevice, type Device } from './device'
import { FebClient, defaultHttp, type HttpGet } from './febClient'
import { LiveFeed, type FeedState, type LiveFeedOptions } from './liveFeed'

export type FeedTiming = Pick<LiveFeedOptions, 'intervalMs' | 'waitingIntervalMs' | 'tailPolls' | 'sleep' | 'now'>

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
  /** Called when the match ends, with the last merged FEB document (JSON text) so it can be kept for a later review (issue #407). */
  onFinished?: (lastDocument: string, code: string) => void
  /** Called when the connection ends (the match is over, or the staff disconnects) with the recording the engine kept of the feed (issue #416). */
  onRecording?: (recording: { code: string; recording: unknown; complete: boolean }) => void
}

const RUNNING = new Set<FeedState['kind']>(['connecting', 'waiting', 'live', 'gap'])

export function useLiveFeed({ engine, http = defaultHttp, device = capacitorDevice, onNote, timing, onOutput, restart, onFinished, onRecording }: Options) {
  const [state, setState] = useState<FeedState>({ kind: 'idle' })
  /** Whether the screen is being kept on (null: no connection running). */
  const [awake, setAwake] = useState<boolean | null>(null)
  const feed = useRef<LiveFeed | null>(null)
  const lastDocument = useRef<string | null>(null)
  /** The match being recorded, until its recording is handed over (so a disconnection after the end does not save it twice). */
  const recording = useRef<string | null>(null)

  /** The feed goes silent when stopped, so "disconnected" is reported here. */
  const keepRecording = useCallback(async (complete: boolean) => {
    const code = recording.current
    recording.current = null
    if (code === null) return
    const kept = await engine.recording()
    if (kept) onRecording?.({ code, recording: kept, complete })
  }, [engine, onRecording])

  const disconnect = useCallback(() => {
    feed.current?.stop()
    setState({ kind: 'stopped' })
    void keepRecording(false)
  }, [keepRecording])

  const connect = useCallback(async (code: string) => {
    feed.current?.stop()
    setState({ kind: 'connecting' })
    await restart()
    lastDocument.current = null
    const clock = timing?.now ?? Date.now
    const started = clock()
    const at = () => (clock() - started) / 1000          // seconds since the first poll: the time of the recording
    await engine.beginRecording(code, new Date(started).toISOString())
    recording.current = code
    const next = new LiveFeed({
      ...timing, client: new FebClient(http), code,
      onState: state => {
        setState(state)
        if (state.kind !== 'finished') return
        if (lastDocument.current !== null) onFinished?.(lastDocument.current, code)
        void keepRecording(true)
      },
      onFailure: endpoint => void engine.recordGap(endpoint, at()),
      onDocument: async json => { lastDocument.current = json; onOutput(await engine.update(json, at())) },
    })
    feed.current = next
    void next.start()
  }, [engine, http, timing, onOutput, restart, onFinished, keepRecording])

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
      onNote?.(reason === 'foreground' ? 'La app vuelve a primer plano: se consulta FEB de inmediato' : 'Red recuperada: se consulta FEB de inmediato')
    })
    return () => { cancelled = true; stopListening(); setAwake(null); void device.allowSleep() }
  }, [running, device, onNote])

  return { state, running, awake, connect, disconnect }
}
