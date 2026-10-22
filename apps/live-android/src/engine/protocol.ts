/** Messages between the UI thread and the engine Web Worker. */
import type { LoggedAlert } from './types'

export type WorkerRequest =
  | { id: number; type: 'start'; payload: string }
  | { id: number; type: 'setMode'; payload: string | null }
  | { id: number; type: 'loadReplay'; payload: string }
  | { id: number; type: 'replay'; payload: number }
  | { id: number; type: 'update'; payload: { doc: string; at?: number } }
  | { id: number; type: 'loadRecording'; payload: string }
  | { id: number; type: 'playRecording'; payload: number }
  | { id: number; type: 'beginRecording'; payload: { match: string; startedIso: string } }
  | { id: number; type: 'recordGap'; payload: { endpoint: string; at: number } }
  | { id: number; type: 'recording' }
  | { id: number; type: 'report'; payload: { game: string; alerts: LoggedAlert[]; ownTeamId: string; ruleConfig?: Record<string, unknown> } }

export type WorkerResponse =
  | { id: number; ok: true; result: unknown }
  | { id: number; ok: false; error: string }
