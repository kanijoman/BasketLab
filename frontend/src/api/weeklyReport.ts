/** The weekly report of two teams (a ZIP of PNG): made in the browser with the dataset `weekly-report` on (issue #716), by the server's job otherwise. */
import { API_BASE, getLiveTeamNames, getPlayerStats, getShotRaw, getShotZones, getTeamConsistency, getTeamStats } from './client'
import { fromSource } from '@/datasource/resolve'
import { localLastMatch } from '@/localdata/source'
import type { LastGame, WeeklyData } from '@/lib/weeklyReport'
import type { Row } from '@/lib/weeklyRows'

export interface WeeklyReportProgress {
  status: 'running' | 'done' | 'error'
  step: number
  total: number
  message: string
  error: string | null
}

export type OnProgress = (progress: WeeklyReportProgress) => void

const SHOTS_LIMIT = 10000
const POLL_MS = 1500

/** What the report reads, from the readers the pages use (the published files with the dataset on, the API only when `?data=api` asks for it), the players once for both teams. */
async function readers(collection: string): Promise<WeeklyData> {
  const players = await getPlayerStats(collection)
  return {
    teamStats: async filter => (await getTeamStats(collection, filter)) as unknown as { team_stats: Row[]; opponent_stats: Row[] },
    consistency: async () => (await getTeamConsistency(collection)).own,
    lastMatch: name => localLastMatch(collection, name) as unknown as Promise<LastGame | null>,
    players: async () => players as unknown as Row[],
    shots: (teamId, player) => getShotRaw(collection, { team_id: teamId, player, limit: SHOTS_LIMIT }),
    zones: (teamId, player) => getShotZones(collection, { team_id: teamId, player, compare: 'league' }),
  }
}

async function inBrowser(collection: string, teamA: string, teamB: string, onProgress?: OnProgress): Promise<Blob> {
  const [{ weeklyReportZip }, { svgToPng }, teams, data] = await Promise.all([import('@/lib/weeklyReport'), import('@/lib/svgImage'), getLiveTeamNames(collection), readers(collection)])
  const a = teams.find(t => t.id === teamA), b = teams.find(t => t.id === teamB)
  if (!a || !b) throw new Error('Uno de los equipos no está en esta competición.')
  return weeklyReportZip({ teamA: a, teamB: b, today: new Date() }, data, svg => svgToPng(svg), (step, total, message) => onProgress?.({ status: 'running', step, total, message, error: null }))
}

const failed = (res: Response) => new Error(`HTTP ${res.status}`)

/** The server's job: ask for it, watch it until it is done and download its ZIP. */
async function onServer(collection: string, teamA: string, teamB: string, onProgress?: OnProgress): Promise<Blob> {
  const start = await fetch(`${API_BASE}/reports/${encodeURIComponent(collection)}/weekly-report`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ team_a: teamA, team_b: teamB }),
  })
  if (!start.ok) throw failed(start)
  const { job_id: job } = (await start.json()) as { job_id: string }
  for (;;) {
    await new Promise(resolve => setTimeout(resolve, POLL_MS))
    const res = await fetch(`${API_BASE}/reports/weekly-report-progress/${encodeURIComponent(job)}`)
    if (!res.ok) throw failed(res)
    const progress = (await res.json()) as WeeklyReportProgress
    onProgress?.(progress)
    if (progress.status === 'error') throw new Error(progress.error ?? 'Error desconocido')
    if (progress.status === 'done') break
  }
  const zip = await fetch(`${API_BASE}/reports/weekly-report-download/${encodeURIComponent(job)}`)
  if (!zip.ok) throw failed(zip)
  return zip.blob()
}

export const downloadWeeklyReport = (collection: string, teamA: string, teamB: string, onProgress?: OnProgress): Promise<Blob> =>
  fromSource('weekly-report', () => inBrowser(collection, teamA, teamB, onProgress), () => onServer(collection, teamA, teamB, onProgress))
