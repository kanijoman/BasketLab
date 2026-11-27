/** Rival scouting report (issue #299): the published report of any team, the matchup computed on the device and the PDF made in the browser. */
import { getTeamStats } from './client'
import { getPointsByOrigin } from './pbpExtended'
import { DataUnavailable, fromSource } from '@/datasource/resolve'
import { compareTeams, STAT_CATALOG, type ComparisonRow } from '@/lib/scoutingCompare'
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

/** The PDF of a report, made in the browser from the report itself (issue #715: no job and no server; jsPDF is loaded when the button is pressed). */
export async function downloadScoutingPdf(report: ScoutingReport): Promise<Blob> {
  const { scoutingPdf } = await import('@/lib/scoutingPdf')
  return scoutingPdf(report, { subtitle: report.collection, ownName: report.own_team?.name ?? 'Nuestro equipo' })
}

/**
 * The scopes the scouting of a team is published for (`liga`, `copa`, `todo`), with the dataset `scouting` on (`?data=local`, issue #638); none when it is
 * off or the publication cannot say, so that the page keeps its job-based flow. An access error (no key) reaches the page.
 */
export const getScoutingScopes = (collection: string, teamId: string): Promise<ScoutingScope[]> =>
  fromSource<ScoutingScope[]>('scouting', () => loadScoutingScopes(collection, teamId), () => [])

/** The published scouting of a team for a scope, or `null` when it is off or cannot be had (with the API asked for on purpose, the page generates it as always). */
export const getPublishedScouting = (collection: string, teamId: string, scope: ScoutingScope): Promise<ScoutingReport | null> =>
  fromSource<ScoutingReport | null>('scouting', () => loadWebScouting(collection, teamId, scope), () => null)

/** The stats of the play-by-play that complete the season rows (the group `Origen de los puntos` of the catalog, as `PBP_KEYS` of the server). */
const PBP_KEYS = STAT_CATALOG.filter(stat => stat.group === 'Origen de los puntos').map(stat => stat.key)

const idOf = (row: Record<string, unknown>): string => String(row.team_id ?? row._id)

/**
 * The matchup of our team against the rival, stat by stat (issue #751: it was a job on the server). It is computed on the device from what the web already reads: the season rows
 * of the competition and, as an enrichment, the play-by-play figures (`ScoutingRivalService._rows`). Without the row of a team there is nothing to compare. An access error (no key)
 * reaches the page; the play-by-play figures not being published only leaves those stats out.
 */
export async function getOwnComparison(collection: string, ownId: string, rivalId: string): Promise<ComparisonRow[]> {
  const { team_stats: seasonRows } = await getTeamStats(collection)
  const wanted = new Set([String(ownId), String(rivalId)])
  const rows: Record<string, Record<string, unknown>> = {}
  for (const row of seasonRows as unknown as Record<string, unknown>[]) if (wanted.has(idOf(row))) rows[idOf(row)] = { ...row }
  try {
    for (const row of (await getPointsByOrigin(collection)) as unknown as Record<string, unknown>[]) {
      const target = rows[String(row.team_id)]
      if (target) for (const key of PBP_KEYS) if (row[key] !== null && row[key] !== undefined) target[key] = row[key]
    }
  } catch (error) {
    if (!(error instanceof DataUnavailable)) throw error                  // no key: the reader must unlock; «not published» only leaves those stats out
  }
  return compareTeams(rows[String(ownId)], rows[String(rivalId)])
}
