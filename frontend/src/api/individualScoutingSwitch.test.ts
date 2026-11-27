import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { strFromU8, unzipSync } from 'fflate'
import { downloadIndividualScoutingDocx } from './individualScouting'
import * as client from './client'
import * as web from '@/webdata/client'
import * as source from '@/localdata/source'
import { DataUnavailable } from '@/datasource/resolve'

const raster = vi.hoisted(() => ({ svgToPng: vi.fn() }))
vi.mock('@/lib/svgImage', async importOriginal => ({ ...(await importOriginal<typeof import('@/lib/svgImage')>()), svgToPng: raster.svgToPng }))
const TINY_PNG = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), c => c.charCodeAt(0))

// The DOCX of the individual scouting is made in the browser with the dataset `scouting` on (issue #717, 17b): the players of the competition, the name of the team and the published images
// (when there are none — an older season, FBCYL — the document is made without them). With it off, the server makes it as always.
const FEB = 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico'
const PLAYERS = [1, 2, 3, 4, 5].map(i => ({ player_id: String(i), player_name: `JUGADOR ${i}`, team_id: i < 4 ? '101' : '102', team_name: i < 4 ? 'ALFA' : 'BRAVO', games_played: 10, points_per_game: i })) as never[]

beforeEach(() => {
  localStorage.clear()
  raster.svgToPng.mockReset().mockResolvedValue(TINY_PNG)
  vi.spyOn(client, 'getShotRaw').mockResolvedValue([])                    // a test that wants shots says so; none must reach the network
  vi.spyOn(source, 'loadCompetition').mockResolvedValue(null)             // the rows of the competition (for the notes of #1083): a test that wants them says so
})
afterEach(() => vi.restoreAllMocks())

async function text(blob: Blob) {
  return strFromU8(unzipSync(new Uint8Array(await blob.arrayBuffer()))['word/document.xml'])
}

describe('the DOCX of the individual scouting', () => {
  const imagesWith = (players: Record<string, Record<string, unknown>>) => ({ format: 1, collection: FEB, team_id: '101', team: 'ALFA', logo: null, players }) as never
  const person = (extra: Record<string, unknown>) => ({ name: null, no: null, photo: null, birth_date: null, height: null, ...extra })

  it('on: a player whose line of the FEB has a baja already reached has no page, and the others do (#1082)', async () => {
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockResolvedValue(imagesWith({ '1': person({ baja: '2026-01-10' }), '2': person({ baja: '2999-01-01' }), '3': person({}) }))   // 2: a baja still to come
    const xml = await text(await downloadIndividualScoutingDocx(FEB, '101'))
    expect(xml).not.toContain('JUGADOR 1')
    expect(xml).toContain('JUGADOR 2')
    expect(xml).toContain('JUGADOR 3')
  })

  it('on: a team whose players all left is not made: there is nobody to scout', async () => {
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockResolvedValue(imagesWith({ '1': person({ baja: '2026-01-10' }), '2': person({ baja: '2026-01-10' }), '3': person({ baja: '2026-01-10' }) }))
    await expect(downloadIndividualScoutingDocx(FEB, '101')).rejects.toThrow('El equipo no tiene jugadores')
  })

  it('on: the notes carry the games a player has missed, counted from his alta, and nothing for who played the last one (#1083)', async () => {
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockResolvedValue(imagesWith({ '3': person({ alta: '2026-10-20' }) }))
    const game = (id: number, day: string) => ({ match_id: id, team_id: '101', starttime: `${day} - 18:00` })
    vi.spyOn(source, 'loadCompetition').mockResolvedValue({ format: 1, collection: FEB, league: 'feb', games: 4, team_rows: [game(1, '04-10-2026'), game(2, '18-10-2026'), game(3, '25-10-2026'), game(4, '01-11-2026')],
      player_rows: [{ match_id: 1, player_id: '1', team_id: '101' }, { match_id: 4, player_id: '2', team_id: '101' }] as never } as never)
    const xml = await text(await downloadIndividualScoutingDocx(FEB, '101'))
    expect(xml).toContain('JUGADOR 1 llega desde 18-10-2026 sin jugar (3 partidos)')      // 1 played only the first
    expect(xml).not.toContain('JUGADOR 2 llega')                                         // 2 played the last one
    expect(xml).toContain('JUGADOR 3 llega desde 25-10-2026 sin jugar (2 partidos)')      // 3 signed on 20-10: the games before do not count
  })

  it('on: it is made here from the players of the competition and the images of the team', async () => {
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
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockRejectedValue(new DataUnavailable('Este informe no está publicado.'))
    expect(await text(await downloadIndividualScoutingDocx(FEB, '101'))).toContain('[FOTO]')
  })

  it('on, with no key for the images: the reader must unlock, the document is not made half blank', async () => {
    vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: 'ALFA' }])
    vi.spyOn(web, 'loadWebImages').mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(downloadIndividualScoutingDocx(FEB, '101')).rejects.toBeInstanceOf(ScopedAccessError)
  })

  describe('the charts of each player', () => {
    const ZONES = [{ zone: 'key_area', zone_label: 'Pintura', points: 2, fga: 5, fgm: 3, fg_pct: 60, rating: 'average', low_sample: true }]
    const SHOT = [{ x: 7, y: 3, made: true, zone: 'key_area' }]
    function setUp(collection: string) {
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

})
