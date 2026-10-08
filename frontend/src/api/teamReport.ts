/** Rule-based team report (own-team analysis / rival scouting). */
import { API_BASE } from './client'

export type ReportMode = 'own' | 'rival'

export interface ReportFinding {
  key: string
  label: string
  formatted: string
  quartile: number
  diff_pct: number | null
  kind: 'strength' | 'weakness'
  text: string
}

export interface ReportDifferential {
  key: string
  label: string
  formatted: string
  diff_pct: number
  advantage: boolean
}

export interface ReportConsistency {
  key: string
  label: string
  cv: number
  status: 'inconsistent' | 'consistent'
  text: string
}

export interface ReportAction {
  key: string
  label: string
  area: 'ofensiva' | 'defensiva'
  kind: 'improve' | 'leverage' | 'neutralize' | 'exploit'
  text: string
  priority?: number
}

export interface TeamReport {
  team: string
  mode: ReportMode
  games_played: number
  strengths: ReportFinding[]
  weaknesses: ReportFinding[]
  differentials: ReportDifferential[]
  consistency: ReportConsistency[]
  profile: string[]
  tactics: ReportAction[]
  training: ReportAction[]
}

function url(collection: string, teamId: string, mode: ReportMode, suffix = ''): string {
  const params = new URLSearchParams({ team_id: teamId, mode })
  return `${API_BASE}/reports/team-report/${encodeURIComponent(collection)}${suffix}?${params}`
}

async function failure(res: Response): Promise<Error> {
  const body = await res.json().catch(() => ({}))
  return new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`)
}

export async function getTeamReport(collection: string, teamId: string, mode: ReportMode): Promise<TeamReport> {
  const res = await fetch(url(collection, teamId, mode))
  if (!res.ok) throw await failure(res)
  return res.json() as Promise<TeamReport>
}

export async function downloadTeamReportPdf(collection: string, teamId: string, mode: ReportMode): Promise<Blob> {
  const res = await fetch(url(collection, teamId, mode, '/pdf'))
  if (!res.ok) throw await failure(res)
  return res.blob()
}
