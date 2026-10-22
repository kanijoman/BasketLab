/**
 * LiveBridge: the typed JS side of src/live_core/session.py.
 *
 * Runs wherever a Pyodide instance exists (the Web Worker in the app, Node in the tests).
 * Only strings cross the boundary: JSON in, JSON out.
 */
import type { EngineOutput, LoggedAlert, PostMatchReport, RecordingFrame, RecordingInfo, ReplayInfo, SessionMeta } from './types'

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
  private readonly fn: Record<
    'start_json' | 'set_mode_json' | 'load_replay_json' | 'replay_json' | 'update_json' | 'load_recording_json' | 'play_recording_json' | 'report_json'
    | 'begin_recording_json' | 'record_gap_json' | 'recording_json',
    PyFn
  >

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
      set_mode_json: get('set_mode_json'),
      load_replay_json: get('load_replay_json'),
      replay_json: get('replay_json'),
      update_json: get('update_json'),
      load_recording_json: get('load_recording_json'),
      play_recording_json: get('play_recording_json'),
      report_json: get('report_json'),
      begin_recording_json: get('begin_recording_json'),
      record_gap_json: get('record_gap_json'),
      recording_json: get('recording_json'),
    }
  }

  /** Alert mode (issue #130); null is the default one. It applies to the sessions started after and to the running one. */
  private mode: string | null = null
  private started = false

  setMode(mode: string | null): Record<string, never> {
    this.mode = mode
    if (this.started) this.fn.set_mode_json(mode)
    return {}
  }

  start(packageText: string): SessionMeta {
    const meta = JSON.parse(this.fn.start_json(packageText, this.mode))
    this.started = true
    return meta
  }

  loadReplay(gameJson: string): ReplayInfo {
    return JSON.parse(this.fn.load_replay_json(gameJson))
  }

  replay(elapsed: number): EngineOutput {
    return JSON.parse(this.fn.replay_json(elapsed))
  }

  /** ``at``: seconds since the first poll of the feed; with it the document goes into the recording that ``beginRecording`` started (issue #416). */
  update(docJson: string, at?: number): EngineOutput {
    return JSON.parse(at === undefined ? this.fn.update_json(docJson) : this.fn.update_json(docJson, at))
  }

  /** The documents ``update`` is given a time for are kept as a recording of this feed (same format as the CI recorder's). */
  beginRecording(match: string, startedIso: string): void {
    this.fn.begin_recording_json(match, startedIso)
  }

  /** ``endpoint`` (boxscore, shotchart, keyfacts) failed ``at`` seconds after the first poll. */
  recordGap(endpoint: string, at: number): void {
    this.fn.record_gap_json(endpoint, at)
  }

  /** The recording so far (the ``recorded_feed`` format) or null when no document has been recorded. */
  recording(): unknown {
    return JSON.parse(this.fn.recording_json())
  }

  loadRecording(recordingJson: string): RecordingInfo {
    return JSON.parse(this.fn.load_recording_json(recordingJson))
  }

  /** The engine fed with what FEB served `t` seconds after the first poll of the recording. */
  playRecording(t: number): RecordingFrame {
    return JSON.parse(this.fn.play_recording_json(t))
  }

  /** The post-match report (issue #409) of a finished game, from the point of view of ``ownTeamId``; it needs no running session. */
  report(gameJson: string, alerts: LoggedAlert[], ownTeamId: string, ruleConfig?: Record<string, unknown>): PostMatchReport {
    return JSON.parse(this.fn.report_json(gameJson, JSON.stringify(alerts), ownTeamId, ruleConfig ? JSON.stringify(ruleConfig) : undefined))
  }
}
