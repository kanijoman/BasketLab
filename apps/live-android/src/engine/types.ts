/** Shapes produced by src/live_core/session.py (JSON across the Pyodide boundary). */

export interface TeamRef {
  id: string
  name: string
}

export interface SessionMeta {
  package_id: string
  schema_version: number
  /** Short hash of the engine sources that run in the app (see src/live_core/version.py). */
  engine_version?: string
  created_at: string
  collection: string
  season: string
  team: TeamRef
  rival: TeamRef
  /** Local team of the match of the package (null: the first document will say). */
  home_id?: string | null
}

export interface ReplayInfo {
  /** Game length in game-seconds (includes overtime). */
  duration: number
  status: string
}

/** A packed real recording loaded for playback (src/live_core/recorded_feed.py). */
export interface RecordingInfo extends ReplayInfo {
  match: string
  frames: number
  /** Seconds in which the first play-by-play line appears: the minutes before are the match waiting to start (issue #346). Absent: 0. */
  start_at?: number
  /** Seconds of the moments in which something new appears in the feed, sorted: the steps of «Siguiente evento» (issue #345). */
  events?: number[]
}

/** One moment of the recording: the engine output, or why there is none (not started yet / FEB answered 404). */
export interface RecordingFrame {
  feed: 'ok' | 'waiting' | 'gap'
  output: EngineOutput | null
}

export type Severity = 'critical' | 'warning' | 'info'

/** What an alert proposes: `sub` (out → in), `timeout` (`left` = timeouts left), `tactic` (`message`, optional target
 *  player); any other `type` is shown by its `message`. */
export interface Proposal {
  type: string
  out_id?: string
  out_name?: string
  in_id?: string
  in_name?: string
  left?: number
  message?: string
  player_id?: string
  player_name?: string
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
  /** Evaluations in a row the engine needed to see the alert before saying it (1 for most). */
  confirm?: number
}

export interface Snapshot {
  period: number
  /** Seconds left in the period. */
  remaining: number
  /** Game-seconds since tip-off. */
  elapsed: number
  score: Record<string, number>
  /** Local team (the first of FEB's header): the engine says it because the JSON boundary sorts keys. */
  home_id?: string | null
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

/** Phase of the match and the timeouts each team has left (FIBA budget), from src/live_core/game_context.py + timeouts.py. */
export interface GameContext {
  phase: 'normal' | 'close_late' | 'decided'
  /** Own score minus rival score. */
  margin: number
  /** Seconds left in the current period. */
  remaining_s: number
  timeouts: { own: number; rival: number | null }
}

/** Formación players on court against the competition's minimum, from src/live_core/rules_lineup.py. */
export interface FormationStatus {
  /** Minimum on court at all times (0: the competition has no such rule; the engine then sends nothing). */
  min: number
  /** False when the package has no FEB roster of our team: the lineup is not watched. */
  known: boolean
  on_court: number | null
  /** On-court players the roster does not settle (they get the benefit of the doubt). */
  unknown: number
  /** Own players on court now (5 unless a substitution is in progress). */
  players: number
  /** The same for the rival (issue #322: the rule watches both teams); missing in an engine that predates it. */
  rival?: { known: boolean; on_court: number | null; unknown: number; players: number }
}

/** Win probability of the own team, from src/live_core/win_prob.py (issue #254; experimental in the app, #257). */
export interface WinProb {
  p: number
  /** Expected final margin (own minus rival). */
  projected_margin: number
  sd: number
  poss_remaining: number
  mu_per_100: number
  /** False until the game has enough possessions: the figure rests on the pre-game prior and the score. */
  reliable: boolean
}

/** What moves the win probability in our favour (issue #256): a Four Factors factor or the pace. */
export interface WinLever {
  id: 'efg' | 'tov' | 'orb' | 'ftr' | 'pace' | string
  /** Probability gain (0-1) if the factor goes back to its usual level, or with the pace change. */
  gain: number
  gain_pts: number
  /** Pace only: who is behind wants it faster ('up'), who is ahead slower ('down'). */
  direction?: 'up' | 'down'
  /** Factor levers: the recommender's substitutions for it. */
  proposal?: Proposal[]
}

export interface EngineOutput {
  snapshot: Snapshot
  alerts: Alert[]
  analysis: {
    four_factors?: { reliable: boolean; lever?: string | null; [key: string]: unknown }; pace?: PaceAnalysis; context?: GameContext
    formation?: FormationStatus; win_prob?: WinProb; win_levers?: WinLever[]
  }
}
