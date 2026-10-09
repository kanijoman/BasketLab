/** Live preparation package: build (background job), poll, download the encrypted file. */
import { API_BASE } from './client'

export interface LivePackageRequest {
  collection: string
  team_id: string
  rival_id: string
  passphrase: string
  /** FEB match the package is prepared for (from the calendar list). */
  match_code?: string
}

export interface LivePackageProgress {
  status: 'running' | 'done' | 'error'
  current: number
  total: number
  team: string
  rival: string
  error: string | null
}

async function failure(res: Response): Promise<Error> {
  const body = await res.json().catch(() => ({}))
  const d = (body as { detail?: unknown }).detail
  if (typeof d === 'string') return new Error(d)
  if (Array.isArray(d)) return new Error(d.map(e => (e as { msg?: string }).msg ?? JSON.stringify(e)).join('; '))
  return new Error(`HTTP ${res.status}`)
}

export async function startLivePackage(req: LivePackageRequest): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/live/package`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<{ job_id: string }>
}

export async function getLivePackageProgress(jobId: string): Promise<LivePackageProgress> {
  const res = await fetch(`${API_BASE}/live/package/progress/${encodeURIComponent(jobId)}`)
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<LivePackageProgress>
}

export async function downloadLivePackage(jobId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/live/package/download/${encodeURIComponent(jobId)}`)
  if (!res.ok) throw await failure(res)
  return res.blob()
}

export interface LiveMatch {
  code: string
  status: 'scheduled' | 'live'
  /** Madrid local time "YYYY-MM-DDTHH:MM"; null for a match already in progress. */
  start: string | null
  round: number
  is_home: boolean
  opponent: { id: string; name: string } | null
  home: { id: string; name: string }
  away: { id: string; name: string }
  starts_in_min: number | null
}

export interface LiveMatches {
  matches: LiveMatch[]
  calendar_url: string | null
  warning: string | null
}

/** Upcoming and in-progress matches of a team, from the FEB calendar. */
export async function getLiveMatches(collection: string, teamId: string, limit = 5): Promise<LiveMatches> {
  const params = new URLSearchParams({ team_id: teamId, limit: String(limit) })
  const res = await fetch(`${API_BASE}/live/matches/${encodeURIComponent(collection)}?${params}`)
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<LiveMatches>
}
