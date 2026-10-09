/** Shapes produced by src/live_core/session.py (JSON across the Pyodide boundary). */

export interface TeamRef {
  id: string
  name: string
}

export interface SessionMeta {
  package_id: string
  schema_version: number
  created_at: string
  collection: string
  season: string
  team: TeamRef
  rival: TeamRef
}

export interface ReplayInfo {
  /** Game length in game-seconds (includes overtime). */
  duration: number
  status: string
}

export type Severity = 'critical' | 'warning' | 'info'

export interface Proposal {
  type: string
  out_id?: string
  out_name?: string
  in_id?: string
  in_name?: string
  [key: string]: unknown
}

export interface Alert {
  key: string
  id: string
  severity: Severity
  category: string
  message: string
  evidence: Record<string, unknown>
  proposal: Proposal[]
  rearm_s: number | null
}

export interface Snapshot {
  period: number
  /** Seconds left in the period. */
  remaining: number
  /** Game-seconds since tip-off. */
  elapsed: number
  score: Record<string, number>
  teams: Record<string, { name: string; fouls_game: number }>
  [key: string]: unknown
}

export interface EngineOutput {
  snapshot: Snapshot
  alerts: Alert[]
  analysis: { four_factors?: { reliable: boolean; lever?: string | null; [key: string]: unknown } }
}
