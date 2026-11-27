/** The weekly report of two teams (a ZIP of PNG): made in the browser with the dataset `weekly-report` on (issue #716), by the server's job otherwise. */
import { getLiveTeamNames, getPlayerStats, getShotRaw, getShotZones, getTeamConsistency, getTeamStats } from './client'
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

/** What the report reads, from the readers the pages use (the published files), the players once for both teams. */
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

export const downloadWeeklyReport = (collection: string, teamA: string, teamB: string, onProgress?: OnProgress): Promise<Blob> =>
  fromSource('weekly-report', () => inBrowser(collection, teamA, teamB, onProgress))
