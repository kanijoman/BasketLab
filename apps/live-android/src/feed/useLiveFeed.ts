/** React side of the live feed: owns the LiveFeed of the running connection and exposes its state. */
import { useCallback, useEffect, useRef, useState } from 'react'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { FebClient, defaultHttp, type HttpGet } from './febClient'
import { LiveFeed, type FeedState, type LiveFeedOptions } from './liveFeed'

export type FeedTiming = Pick<LiveFeedOptions, 'intervalMs' | 'waitingIntervalMs' | 'tailPolls' | 'sleep' | 'now'>

interface Options {
  engine: EngineApi
  http?: HttpGet
  timing?: FeedTiming
  /** Called with the engine output of every document of the feed. */
  onOutput: (output: EngineOutput) => void
  /** Called before connecting: gives the engine a fresh session and clears what the screen shows. */
  restart: () => Promise<void>
}

const RUNNING = new Set<FeedState['kind']>(['connecting', 'waiting', 'live', 'gap'])

export function useLiveFeed({ engine, http = defaultHttp, timing, onOutput, restart }: Options) {
  const [state, setState] = useState<FeedState>({ kind: 'idle' })
  const feed = useRef<LiveFeed | null>(null)

  /** The feed goes silent when stopped, so "disconnected" is reported here. */
  const disconnect = useCallback(() => {
    feed.current?.stop()
    setState({ kind: 'stopped' })
  }, [])

  const connect = useCallback(async (code: string) => {
    feed.current?.stop()
    setState({ kind: 'connecting' })
    await restart()
    const next = new LiveFeed({
      ...timing, client: new FebClient(http), code, onState: setState,
      onDocument: async json => onOutput(await engine.update(json)),
    })
    feed.current = next
    void next.start()
  }, [engine, http, timing, onOutput, restart])

  useEffect(() => () => feed.current?.stop(), [])

  return { state, running: RUNNING.has(state.kind), connect, disconnect }
}
