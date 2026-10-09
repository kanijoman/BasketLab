/**
 * LiveBridge: the typed JS side of src/live_core/session.py.
 *
 * Runs wherever a Pyodide instance exists (the Web Worker in the app, Node in the tests).
 * Only strings cross the boundary: JSON in, JSON out.
 */
import type { EngineOutput, ReplayInfo, SessionMeta } from './types'

/** The part of the Pyodide API the bridge uses. */
export interface PyodideLike {
  FS: { mkdirTree(path: string): void; writeFile(path: string, data: string): void }
  runPython(code: string): unknown
}

export interface EngineBundle {
  /** file name -> Python source of src/live_core */
  files: Record<string, string>
}

type PyFn = (...args: unknown[]) => string

export class LiveBridge {
  private readonly fn: Record<'start_json' | 'load_replay_json' | 'replay_json' | 'update_json', PyFn>

  constructor(py: PyodideLike, bundle: EngineBundle) {
    py.FS.mkdirTree('/app/src/live_core')
    py.FS.writeFile('/app/src/__init__.py', '')
    for (const [name, source] of Object.entries(bundle.files)) {
      py.FS.writeFile(`/app/src/live_core/${name}`, source)
    }
    py.runPython('import sys\nif "/app" not in sys.path: sys.path.insert(0, "/app")')
    const get = (name: string) => py.runPython(`from src.live_core import session as _s\n_s.${name}`) as PyFn
    this.fn = {
      start_json: get('start_json'),
      load_replay_json: get('load_replay_json'),
      replay_json: get('replay_json'),
      update_json: get('update_json'),
    }
  }

  start(packageText: string): SessionMeta {
    return JSON.parse(this.fn.start_json(packageText))
  }

  loadReplay(gameJson: string): ReplayInfo {
    return JSON.parse(this.fn.load_replay_json(gameJson))
  }

  replay(elapsed: number): EngineOutput {
    return JSON.parse(this.fn.replay_json(elapsed))
  }

  update(docJson: string): EngineOutput {
    return JSON.parse(this.fn.update_json(docJson))
  }
}
