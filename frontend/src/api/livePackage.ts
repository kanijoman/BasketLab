/** Live preparation package: build (background job), poll, download the encrypted file. */
import { API_BASE } from './client'

export interface LivePackageRequest {
  collection: string
  team_id: string
  rival_id: string
  passphrase: string
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
