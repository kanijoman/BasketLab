import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { strFromU8, unzipSync } from 'fflate'
import { downloadIndividualScoutingDocx } from './individualScouting'
import * as client from './client'
import * as web from '@/webdata/client'
import { DATA_FLAG_KEY } from '@/datasource/switch'
import { DataUnavailable } from '@/datasource/resolve'

const raster = vi.hoisted(() => ({ svgToPng: vi.fn() }))
vi.mock('@/lib/svgImage', async importOriginal => ({ ...(await importOriginal<typeof import('@/lib/svgImage')>()), svgToPng: raster.svgToPng }))
const TINY_PNG = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), c => c.charCodeAt(0))

// The DOCX of the individual scouting is made in the browser with the dataset `scouting` on (issue #717, 17b): the players of the competition, the name of the team and the published images
// (when there are none — an older season, FBCYL — the document is made without them). With it off, the server makes it as always.
const FEB = 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico'
const PLAYERS = [1, 2, 3, 4, 5].map(i => ({ player_id: String(i), player_name: `JUGADOR ${i}`, team_id: i < 4 ? '101' : '102', team_name: i < 4 ? 'ALFA' : 'BRAVO', games_played: 10, points_per_game: i })) as never[]

beforeEach(() => {
  localStorage.clear(); localStorage.setItem('basketlab.data', 'api')
  raster.svgToPng.mockReset().mockResolvedValue(TINY_PNG)
  vi.spyOn(client, 'getShotRaw').mockResolvedValue([])                    // a test that wants shots says so; none must reach the network
})
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
    vi.spyOn(client, 'getShotRaw').mockResolvedValue([])
    const fetched = vi.spyOn(globalThis, 'fetch')
    const xml = await text(await downloadIndividualScoutingDocx(FEB, '101'))
    expect(images).toHaveBeenCalledWith(FEB, '101')
    expect(xml).toContain('Scouting Individual — ALFA')
    expect(xml).toContain('JUGADOR 3')
    expect(xml).not.toContain('JUGADOR 4')       // the team asked for, not the others
    expect(xml).toContain('05/03/1998')
    expect(fetched).not.toHaveBeenCalled()
  })

  it('on: it reports its progress, the charts of each player and then the document (#215)', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockResolvedValue(null as never)
    const seen: unknown[] = []
    await downloadIndividualScoutingDocx(FEB, '101', p => seen.push(p))
    expect(seen).toEqual([
      { stage: 'charts', current: 0, total: 3 },
      { stage: 'charts', current: 1, total: 3 }, { stage: 'charts', current: 2, total: 3 }, { stage: 'charts', current: 3, total: 3 },
      { stage: 'document', current: 3, total: 3 },
    ])
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

  describe('the charts of each player', () => {
    const ZONES = [{ zone: 'paint', zone_label: 'Pintura', points: 2, fga: 5, fgm: 3, fg_pct: 60, rating: 'average', low_sample: true }]
    const SHOT = [{ x: 7, y: 3, made: true, zone: 'paint' }]
    function setUp(collection: string) {
      localStorage.setItem(DATA_FLAG_KEY, 'local')
      vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
      vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
      vi.spyOn(web, 'loadWebImages').mockRejectedValue(new DataUnavailable('no'))
      const raw = vi.spyOn(client, 'getShotRaw').mockImplementation(async (_c, p) => (p.player === '2' ? [] : (SHOT as never)))
      const zones = vi.spyOn(client, 'getShotZones').mockResolvedValue(ZONES as never)
      return { raw, zones, collection }
    }

    it('are the radar of every player and, for those with shots, the heatmap and the zones against the league', async () => {
      const { raw, zones } = setUp(FEB)
      const xml = await text(await downloadIndividualScoutingDocx(FEB, '101'))
      expect(raw).toHaveBeenCalledWith(FEB, { team_id: '101', player: '1', limit: 10000 })
      expect(zones).toHaveBeenCalledWith(FEB, { team_id: '101', player: '1', compare: 'league' })
      expect((xml.match(/4\. Perfil de Juego/g) ?? []).length).toBe(3)
      expect((xml.match(/3\. Perfil de Lanzamiento/g) ?? []).length).toBe(2)                // the player 2 has no shots: no profile
      expect(raster.svgToPng).toHaveBeenCalledTimes(3 + 2 * 2)
    })

    it('have no shooting profile in FBCYL (the server never made it) but have the radar', async () => {
      const { raw } = setUp('FBCYL_1ª_FASE-GRUPO_A-1_2026_')
      const xml = await text(await downloadIndividualScoutingDocx('FBCYL_1ª_FASE-GRUPO_A-1_2026_', '101'))
      expect(raw).not.toHaveBeenCalled()
      expect(xml).toContain('4. Perfil de Juego')
      expect(xml).not.toContain('3. Perfil de Lanzamiento')
    })

    it('that the browser cannot draw are left out of the document, which is still made', async () => {
      setUp(FEB)
      raster.svgToPng.mockRejectedValue(new Error('sin canvas'))
      const xml = await text(await downloadIndividualScoutingDocx(FEB, '101'))
      expect(xml).toContain('JUGADOR 1')
      expect(xml).not.toContain('Perfil de')
    })

    it('are not made without the key of the shots: the reader must unlock', async () => {
      const { raw } = setUp(FEB)
      raw.mockRejectedValue(new ScopedAccessError('sin clave'))
      await expect(downloadIndividualScoutingDocx(FEB, '101')).rejects.toBeInstanceOf(ScopedAccessError)
    })
  })

  it('off: the server makes it and its failure is said', async () => {
    const fetched = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'FEB no responde' }), { status: 502 }))
    await expect(downloadIndividualScoutingDocx(FEB, '101')).rejects.toThrow('FEB no responde')
    expect(String(fetched.mock.calls[0][0])).toContain('/reports/individual-scouting/docx?collection=')
    fetched.mockResolvedValueOnce(new Response('docx'))
    expect(await (await downloadIndividualScoutingDocx(FEB, '101')).text()).toBe('docx')
  })
})
