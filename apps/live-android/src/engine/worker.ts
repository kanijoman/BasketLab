/// <reference lib="webworker" />
/**
 * Engine Web Worker: loads Pyodide (bundled with the app, no network) and the live_core
 * sources, then serves requests through LiveBridge. Heavy Python never runs on the UI thread.
 */
import { loadPyodide } from 'pyodide'
import { LiveBridge, type EngineBundle } from './bridge'
import type { WorkerRequest, WorkerResponse } from './protocol'

const origin = self.location.origin

async function createBridge(): Promise<LiveBridge> {
  const [pyodide, bundle] = await Promise.all([
    loadPyodide({ indexURL: `${origin}/pyodide/` }),
    fetch(`${origin}/engine/live_core.json`).then(r => r.json() as Promise<EngineBundle>),
  ])
  return new LiveBridge(pyodide, bundle)
}

const ready = createBridge()

function run(bridge: LiveBridge, msg: WorkerRequest): unknown {
  switch (msg.type) {
    case 'start': return bridge.start(msg.payload)
    case 'loadReplay': return bridge.loadReplay(msg.payload)
    case 'replay': return bridge.replay(msg.payload)
    case 'update': return bridge.update(msg.payload)
  }
}

// Requests are served strictly in order (Python is single-threaded).
let queue: Promise<void> = Promise.resolve()

self.onmessage = (e: MessageEvent<WorkerRequest>) => {
  const msg = e.data
  queue = queue.then(async () => {
    let response: WorkerResponse
    try {
      response = { id: msg.id, ok: true, result: run(await ready, msg) }
    } catch (err) {
      response = { id: msg.id, ok: false, error: err instanceof Error ? err.message : String(err) }
    }
    self.postMessage(response)
  })
}
