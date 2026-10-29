/** Rule-based team report (own-team analysis / rival scouting). */
import { API_BASE, getLiveTeamNames, type TeamEntry } from './client'
import { fromSource } from '@/datasource/resolve'
import { loadReportTeams, loadWebReport } from '@/webdata/client'

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
  n: number
  low_sample: boolean
  text: string
}

export interface ReportZone {
  zone: string
  label: string
  points: number | null
  fga: number
  fg_pct: number | null
  league_pct: number | null
  delta_pp: number | null
  low_sample: boolean
  kind: 'hot' | 'cold'
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
  /** Few games played: values are indicative only (early season). */
  low_sample: boolean
  strengths: ReportFinding[]
  weaknesses: ReportFinding[]
  differentials: ReportDifferential[]
  consistency: ReportConsistency[]
  zones: ReportZone[]
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

/**
 * The report of a team. With the dataset `team-report` on (`?data=local`) it is the one published in `web-data`, opened with the open key of the beta or
 * the invitations of the reader (issue #639); when that cannot answer it asks the API as always. An access error (`ScopedAccessError`) is NOT answered
 * by the API (`fromSource`): the page must tell the reader to unlock, otherwise the keys would mean nothing while the server still serves everything.
 */
export const getTeamReport = (collection: string, teamId: string, mode: ReportMode): Promise<TeamReport> =>
  fromSource('team-report', () => loadWebReport(collection, teamId, mode), async () => {
    const res = await fetch(url(collection, teamId, mode))
    if (!res.ok) throw await failure(res)
    return res.json() as Promise<TeamReport>
  })

/** The teams to choose from: the ones with a published report with the dataset `report-teams` on (the API's list if it cannot answer), else the API's. */
export const getReportTeams = (collection: string): Promise<TeamEntry[]> =>
  fromSource('report-teams', () => loadReportTeams(collection), () => getLiveTeamNames(collection))

export async function downloadTeamReportPdf(collection: string, teamId: string, mode: ReportMode): Promise<Blob> {
  const res = await fetch(url(collection, teamId, mode, '/pdf'))
  if (!res.ok) throw await failure(res)
  return res.blob()
}
