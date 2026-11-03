/** The DOCX of the individual scouting of a team (one page per player, blank notes section): made in the browser with the dataset `scouting` on (issue #717), by the server otherwise. */
import { API_BASE, getLiveTeamNames, getPlayerStats } from './client'
import { fromSource, DataUnavailable } from '@/datasource/resolve'
import { loadWebImages, type TeamImages } from '@/webdata/client'

/** The images of the team, or `null` when the publication has none for this competition (an older season, FBCYL): the document is then made without them. */
async function imagesOf(collection: string, teamId: string): Promise<TeamImages | null> {
  try {
    return await loadWebImages(collection, teamId)
  } catch (error) {
    if (error instanceof DataUnavailable) return null
    throw error                                          // no key: the reader must unlock, a half blank document is not what was asked for
  }
}

async function inBrowser(collection: string, teamId: string): Promise<Blob> {
  const [{ scoutingDocx }, players, teams, images] = await Promise.all([import('@/lib/scoutingDocx'), getPlayerStats(collection), getLiveTeamNames(collection), imagesOf(collection, teamId)])
  const today = new Date()
  return scoutingDocx({
    players, teamName: teams.find(t => t.id === teamId)?.name ?? '', images, today,
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

export const downloadIndividualScoutingDocx = (collection: string, teamId: string): Promise<Blob> =>
  fromSource('scouting', () => inBrowser(collection, teamId), () => onServer(collection, teamId))
