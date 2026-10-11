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

/** Game pace (possessions per 40 min), from src/live_core/pace.py. Habits are null in packages that predate them. */
export interface PaceAnalysis {
  reliable: boolean
  possessions: number
  current40: number
  habit_own40: number | null
  habit_rival40: number | null
  /** Current pace minus each team's habitual pace. */
  delta_own: number | null
  delta_rival: number | null
  /** Possessions per team at the end of the game, extrapolating the pace so far over the time left. */
  projected_possessions: number
  sample_games: { own: number | null; rival: number | null }
}

export interface EngineOutput {
  snapshot: Snapshot
  alerts: Alert[]
  analysis: { four_factors?: { reliable: boolean; lever?: string | null; [key: string]: unknown }; pace?: PaceAnalysis }
}
