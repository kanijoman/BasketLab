/** Promise-based client for the engine Web Worker (keeps the UI thread free while Python runs). */
import type { WorkerRequest, WorkerResponse } from './protocol'
import type { EngineOutput, ReplayInfo, SessionMeta } from './types'

export interface EngineApi {
  start(packageText: string): Promise<SessionMeta>
  loadReplay(gameJson: string): Promise<ReplayInfo>
  replay(elapsed: number): Promise<EngineOutput>
  update(docJson: string): Promise<EngineOutput>
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
  loadReplay(gameJson: string) { return this.call<ReplayInfo>({ type: 'loadReplay', payload: gameJson }) }
  replay(elapsed: number) { return this.call<EngineOutput>({ type: 'replay', payload: elapsed }) }
  update(docJson: string) { return this.call<EngineOutput>({ type: 'update', payload: docJson }) }

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
