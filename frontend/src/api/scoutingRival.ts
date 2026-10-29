/** Rival scouting report (issue #299): start the report of any team (background job), poll it, read it and download the PDF. */
import { API_BASE } from './client'
import { fromSource } from '@/datasource/resolve'
import { loadScoutingScopes, loadWebScouting } from '@/webdata/client'

export interface ScoutingRequest {
  collection: string
  /** The team to scout: any team of the collection. */
  team_id: string
  /** Our team, for the matchup comparison (optional). */
  own_team_id?: string
}

export interface ScoutingProgress {
  status: 'running' | 'done' | 'error'
  current: number
  total: number
  team: string
  own_team: string | null
  error: string | null
}

export interface ScoutingKey { area: string; action: 'exploit' | 'neutralize'; text: string }
export interface ScoutingPlanItem { text: string; source: 'informe' | 'motor' }

/** One row of «Origen de los puntos» (per game; ``conceded`` = what its rivals score; deltas in % against the league). */
export interface ScoutingOriginRow {
  key: string
  label: string
  own: number | null
  conceded: number | null
  league: number | null
  own_delta_pct: number | null
  conceded_delta_pct: number | null
}

/** What a published scouting counts (issue #638): the league, the cups of the season, or both. */
export type ScoutingScope = 'liga' | 'copa' | 'todo'

/** A game of the scouted team; the competition and the category of the rival are there when the scouting spans several competitions. */
export interface ScoutingGame {
  code: string
  date: string
  opponent_id: string
  opponent: string
  home: boolean
  score_for: number
  score_against: number
  margin: number
  competition?: string
  /** The rival's category minus the team's, and whether it is another one. */
  level_gap?: number
  other_level?: boolean
}

export interface ScoutingReport {
  team: { id: string; name: string }
  own_team: { id: string; name: string } | null
  collection: string
  /** `F` / `M` of the competition (the words agree with it, #495); absent or empty = masculine. */
  gender?: string
  sample_games: number
  /** Which games it counts (published scouting only; the one of the API is the league's). */
  scope?: ScoutingScope
  games: ScoutingGame[]
  low_sample: boolean
  notices: string[]
  record: { wins: number; losses: number; avg_for: number; avg_against: number; avg_margin: number }
  profile: string[]
  keys: ScoutingKey[]
  plan: { neutralize: ScoutingPlanItem[]; exploit: ScoutingPlanItem[] }
  players: { id: string; name: string; games: number; minutes: number; pts: number; pts_per_game: number; share: number; clutch: { pts: number; fga: number } }[]
  lineups: { text: string }[]
  /** Points by origin against the league; empty when the games cannot be trusted for it. */
  origin: ScoutingOriginRow[]
  alerts: { id: string; label: string; text: string }[]
  comparison: { key: string; label: string; group: string; own_text: string; rival_text: string; advantage: 'own' | 'rival' | 'even' | 'neutral' }[]
}

async function failure(res: Response): Promise<Error> {
  const body = await res.json().catch(() => ({}))
  const d = (body as { detail?: unknown }).detail
  if (typeof d === 'string') return new Error(d)
  if (Array.isArray(d)) return new Error(d.map(e => (e as { msg?: string }).msg ?? JSON.stringify(e)).join('; '))
  return new Error(`HTTP ${res.status}`)
}

const job = (path: string, id: string) => `${API_BASE}/scouting-rival/${path}/${encodeURIComponent(id)}`

export async function startScouting(req: ScoutingRequest): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/scouting-rival`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<{ job_id: string }>
}

export async function getScoutingProgress(jobId: string): Promise<ScoutingProgress> {
  const res = await fetch(job('progress', jobId))
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<ScoutingProgress>
}

export async function getScoutingReport(jobId: string): Promise<ScoutingReport> {
  const res = await fetch(job('report', jobId))
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<ScoutingReport>
}

export async function downloadScoutingPdf(jobId: string): Promise<Blob> {
  const res = await fetch(job('pdf', jobId))
  if (!res.ok) throw await failure(res)
  return res.blob()
}

/**
 * The scopes the scouting of a team is published for (`liga`, `copa`, `todo`), with the dataset `scouting` on (`?data=local`, issue #638); none when it is
 * off or the publication cannot say, so that the page keeps its job-based flow. An access error (no key) reaches the page.
 */
export const getScoutingScopes = (collection: string, teamId: string): Promise<ScoutingScope[]> =>
  fromSource<ScoutingScope[]>('scouting', () => loadScoutingScopes(collection, teamId), async () => [])

/** The published scouting of a team for a scope, or `null` when it is off or cannot be had (the page then generates it as always). */
export const getPublishedScouting = (collection: string, teamId: string, scope: ScoutingScope): Promise<ScoutingReport | null> =>
  fromSource<ScoutingReport | null>('scouting', () => loadWebScouting(collection, teamId, scope), async () => null)
