import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { strFromU8, unzipSync } from 'fflate'
import { downloadIndividualScoutingDocx } from './individualScouting'
import * as client from './client'
import * as web from '@/webdata/client'
import { DATA_FLAG_KEY } from '@/datasource/switch'
import { DataUnavailable } from '@/datasource/resolve'

// The DOCX of the individual scouting is made in the browser with the dataset `scouting` on (issue #717, 17b): the players of the competition, the name of the team and the published images
// (when there are none — an older season, FBCYL — the document is made without them). With it off, the server makes it as always.
const FEB = 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico'
const PLAYERS = [1, 2, 3, 4, 5].map(i => ({ player_id: String(i), player_name: `JUGADOR ${i}`, team_id: i < 4 ? '101' : '102', team_name: i < 4 ? 'ALFA' : 'BRAVO', games_played: 10, points_per_game: i })) as never[]

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

async function text(blob: Blob) {
  return strFromU8(unzipSync(new Uint8Array(await blob.arrayBuffer()))['word/document.xml'])
}

describe('the DOCX of the individual scouting', () => {
  it('on: it is made here from the players of the competition and the images of the team', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }, { id: '102', name: 'BRAVO' }])
    const images = vi.spyOn(web, 'loadWebImages').mockResolvedValue({ format: 1, collection: FEB, team_id: '101', team: 'ALFA', logo: null, players: { '1': { name: 'JUGADOR 1', no: '4', photo: null, birth_date: '05/03/1998', height: '198 cm' } } })
    const fetched = vi.spyOn(globalThis, 'fetch')
    const xml = await text(await downloadIndividualScoutingDocx(FEB, '101'))
    expect(images).toHaveBeenCalledWith(FEB, '101')
    expect(xml).toContain('Scouting Individual — ALFA')
    expect(xml).toContain('JUGADOR 3')
    expect(xml).not.toContain('JUGADOR 4')       // the team asked for, not the others
    expect(xml).toContain('05/03/1998')
    expect(fetched).not.toHaveBeenCalled()
  })

  it('on, with no images published for the competition: the document is made without them', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockRejectedValue(new DataUnavailable('Este informe no está publicado.'))
    expect(await text(await downloadIndividualScoutingDocx(FEB, '101'))).toContain('[FOTO]')
  })

  it('on, with no key for the images: the reader must unlock, the document is not made half blank', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(downloadIndividualScoutingDocx(FEB, '101')).rejects.toBeInstanceOf(ScopedAccessError)
  })

  it('off: the server makes it and its failure is said', async () => {
    const fetched = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'FEB no responde' }), { status: 502 }))
    await expect(downloadIndividualScoutingDocx(FEB, '101')).rejects.toThrow('FEB no responde')
    expect(String(fetched.mock.calls[0][0])).toContain('/reports/individual-scouting/docx?collection=')
    fetched.mockResolvedValueOnce(new Response('docx'))
    expect(await (await downloadIndividualScoutingDocx(FEB, '101')).text()).toBe('docx')
  })
})
