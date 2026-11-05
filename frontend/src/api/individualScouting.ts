/** The DOCX of the individual scouting of a team (one page per player, blank notes section): made in the browser with the dataset `scouting` on (issue #717), by the server otherwise. */
import { ScopedAccessError } from '@live-package/crypto'
import { API_BASE, getLiveTeamNames, getPlayerStats, getShotRaw, getShotZones, type PlayerStat } from './client'
import { fromSource, DataUnavailable } from '@/datasource/resolve'
import { loadWebImages, type TeamImages } from '@/webdata/client'
import type { PlayerCharts } from '@/lib/scoutingDocx'

/** The images of the team, or `null` when the publication has none for this competition (an older season, FBCYL): the document is then made without them. */
async function imagesOf(collection: string, teamId: string): Promise<TeamImages | null> {
  try {
    return await loadWebImages(collection, teamId)
  } catch (error) {
    if (error instanceof DataUnavailable) return null
    throw error                                          // no key: the reader must unlock, a half blank document is not what was asked for
  }
}

/** A chart that cannot be had is left out of the page (as the server did): only a missing key is an error, the reader must unlock. */
async function lenient<T>(make: () => Promise<T>): Promise<T | undefined> {
  try {
    return await make()
  } catch (error) {
    if (error instanceof ScopedAccessError) throw error
    return undefined
  }
}

const SHOTS_LIMIT = 10000

/** Where the generation is: the charts of each player (the slow part), then the document. */
export interface DocxProgress { stage: 'charts' | 'document'; current: number; total: number }

/** The charts of each player of the team: his radar against the league and, in FEB (the shots are not charted in FBCYL, as the server never did), the heatmap and the zones of his shots against the league's. */
async function chartsOf(collection: string, teamId: string, roster: PlayerStat[], league: PlayerStat[], onProgress?: (p: DocxProgress) => void): Promise<Record<string, PlayerCharts>> {
  const [{ courtSvg }, { radarModel, radarSvg }, { svgToPng }] = await Promise.all([import('@/lib/scoutingCharts'), import('@/lib/radarChart'), import('@/lib/svgImage')])
  const shooting = !/FBCYL/i.test(collection)
  const charts: Record<string, PlayerCharts> = {}
  onProgress?.({ stage: 'charts', current: 0, total: roster.length })
  for (const [index, player] of roster.entries()) {                                      // one at a time: a player's charts are PNGs of a few hundred KB each
    const id = String(player.player_id)
    const mine: PlayerCharts = {}
    mine.radar = await lenient(() => svgToPng(radarSvg(radarModel(player, league), player.player_name ?? '')))
    const shots = shooting ? await lenient(() => getShotRaw(collection, { team_id: teamId, player: id, limit: SHOTS_LIMIT })) : undefined
    if (shots?.length) {
      const zones = (await lenient(() => getShotZones(collection, { team_id: teamId, player: id, compare: 'league' }))) ?? []
      mine.heatmap = await lenient(() => svgToPng(courtSvg('heatmap', [], shots)))
      mine.zones = await lenient(() => svgToPng(courtSvg('zones', zones, shots)))
    }
    charts[id] = mine
    onProgress?.({ stage: 'charts', current: index + 1, total: roster.length })
  }
  return charts
}

async function inBrowser(collection: string, teamId: string, onProgress?: (p: DocxProgress) => void): Promise<Blob> {
  const [{ scoutingDocx }, players, teams, images] = await Promise.all([import('@/lib/scoutingDocx'), getPlayerStats(collection), getLiveTeamNames(collection), imagesOf(collection, teamId)])
  const today = new Date()
  const teamName = teams.find(t => t.id === teamId)?.name ?? ''
  const roster = players.filter(p => p.team_name === teamName)
  const charts = await chartsOf(collection, teamId, roster, players, onProgress)
  onProgress?.({ stage: 'document', current: roster.length, total: roster.length })
  return scoutingDocx({
    players, teamName, images, charts, today,
    date: today.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' }),
  })
}

async function onServer(collection: string, teamId: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/reports/individual-scouting/docx?${new URLSearchParams({ collection, team_id: teamId })}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'Error descargando DOCX')
  }
  return res.blob()
}

/** The server gives no progress: only the browser reports it (`onProgress`). */
export const downloadIndividualScoutingDocx = (collection: string, teamId: string, onProgress?: (p: DocxProgress) => void): Promise<Blob> =>
  fromSource('scouting', () => inBrowser(collection, teamId, onProgress), () => onServer(collection, teamId))
