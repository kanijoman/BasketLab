/** Promise-based client for the engine Web Worker (keeps the UI thread free while Python runs). */
import type { WorkerRequest, WorkerResponse } from './protocol'
import type { EngineOutput, LoggedAlert, PostMatchReport, RecordingFrame, RecordingInfo, ReplayInfo, SessionMeta } from './types'

export interface EngineApi {
  start(packageText: string): Promise<SessionMeta>
  /** Alert mode of the engine (issue #130): applies to the next session and, if one is running, to it. */
  setMode(mode: string | null): Promise<void>
  loadReplay(gameJson: string): Promise<ReplayInfo>
  replay(elapsed: number): Promise<EngineOutput>
  /** ``at``: seconds since the first poll of the feed; with it the document is recorded (issue #416). */
  update(docJson: string, at?: number): Promise<EngineOutput>
  /** Starts keeping a recording of the feed (the format of the CI recorder) from the documents ``update`` is given a time for. */
  beginRecording(match: string, startedIso: string): Promise<void>
  recordGap(endpoint: string, at: number): Promise<void>
  /** The recording so far, as an object of the recording format, or null. */
  recording(): Promise<unknown>
  loadRecording(recordingJson: string): Promise<RecordingInfo>
  playRecording(t: number): Promise<RecordingFrame>
  /** The post-match report (issue #409) of a finished game (its last FEB document, JSON text) for ``ownTeamId``; needs no running session. */
  report(game: string, alerts: LoggedAlert[], ownTeamId: string): Promise<PostMatchReport>
  dispose(): void
}

interface WorkerLike {
  postMessage(msg: WorkerRequest): void
  terminate(): void
  onmessage: ((e: { data: WorkerResponse }) => void) | null
  onerror: ((e: { message: string }) => void) | null
}

type Pending = { resolve: (v: never) => void; reject: (e: Error) => void }
type Distribute<T> = T extends unknown ? Omit<T, 'id'> : never

export class EngineClient implements EngineApi {
  private readonly worker: WorkerLike
  private readonly pending = new Map<number, Pending>()
  private nextId = 1
  private disposed = false

  constructor(createWorker: () => WorkerLike) {
    this.worker = createWorker()
    this.worker.onmessage = e => this.onMessage(e.data)
    this.worker.onerror = e => this.failAll(new Error(e.message || 'El motor se detuvo'))
  }

  private onMessage(msg: WorkerResponse) {
    const p = this.pending.get(msg.id)
    if (!p) return
    this.pending.delete(msg.id)
    if (msg.ok) p.resolve(msg.result as never)
    else p.reject(new Error(msg.error))
  }

  private failAll(error: Error) {
    for (const p of this.pending.values()) p.reject(error)
    this.pending.clear()
  }

  private call<T>(request: Distribute<WorkerRequest>): Promise<T> {
    if (this.disposed) return Promise.reject(new Error('Engine disposed'))
    return new Promise<T>((resolve, reject) => {
      const id = this.nextId++
      this.pending.set(id, { resolve: resolve as (v: never) => void, reject })
      this.worker.postMessage({ ...request, id } as WorkerRequest)
    })
  }

  start(packageText: string) { return this.call<SessionMeta>({ type: 'start', payload: packageText }) }
  async setMode(mode: string | null) { await this.call<unknown>({ type: 'setMode', payload: mode }) }
  loadReplay(gameJson: string) { return this.call<ReplayInfo>({ type: 'loadReplay', payload: gameJson }) }
  replay(elapsed: number) { return this.call<EngineOutput>({ type: 'replay', payload: elapsed }) }
  update(docJson: string, at?: number) { return this.call<EngineOutput>({ type: 'update', payload: { doc: docJson, at } }) }
  async beginRecording(match: string, startedIso: string) { await this.call<unknown>({ type: 'beginRecording', payload: { match, startedIso } }) }
  async recordGap(endpoint: string, at: number) { await this.call<unknown>({ type: 'recordGap', payload: { endpoint, at } }) }
  recording() { return this.call<unknown>({ type: 'recording' }) }
  loadRecording(recordingJson: string) { return this.call<RecordingInfo>({ type: 'loadRecording', payload: recordingJson }) }
  playRecording(t: number) { return this.call<RecordingFrame>({ type: 'playRecording', payload: t }) }
  report(game: string, alerts: LoggedAlert[], ownTeamId: string) {
    return this.call<PostMatchReport>({ type: 'report', payload: { game, alerts, ownTeamId } })
  }

  dispose() {
    this.disposed = true
    this.failAll(new Error('Engine disposed'))
    this.worker.terminate()
  }
}

/** The real engine: a module Web Worker running Pyodide. */
export function createWorkerEngine(): EngineApi {
  return new EngineClient(
    () => new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' }) as unknown as WorkerLike,
  )
}
