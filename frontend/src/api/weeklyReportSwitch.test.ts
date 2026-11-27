import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { strFromU8, unzipSync } from 'fflate'
import { downloadWeeklyReport } from './weeklyReport'
import * as client from './client'
import * as source from '@/localdata/source'
import vectors from '../../../tests/local_vectors/weekly_rows.json'

const raster = vi.hoisted(() => ({ svgToPng: vi.fn() }))
vi.mock('@/lib/svgImage', async importOriginal => ({ ...(await importOriginal<typeof import('@/lib/svgImage')>()), svgToPng: raster.svgToPng }))

// The weekly report is made in the browser with the dataset `weekly-report` on (issue #716): the tables of the competition, its players and its shots, from the same readers the pages use, and a
// ZIP of the PNG of the server's folders. With it off, the server's job makes it as always and the page only watches its progress.
const COLLECTION = 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico'
const TEAMS = vectors.leagues[0].teams as never[]
const [A, B] = [String((TEAMS[0] as { team_name: string }).team_name), String((TEAMS[1] as { team_name: string }).team_name)]
const PLAYERS = (vectors.leagues[0].players as Record<string, unknown>[]).map((p, i) => ({ ...p, player_id: `p${i}`, team_name: i < 2 ? A : B })) as never[]

beforeEach(() => {
  localStorage.clear()
  raster.svgToPng.mockReset().mockImplementation(async (svg: string) => new TextEncoder().encode(svg))
})
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers() })

function browserData() {
  vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '101', name: A }, { id: '102', name: B }])
  vi.spyOn(client, 'getTeamStats').mockResolvedValue({ team_stats: TEAMS, opponent_stats: TEAMS } as never)
  vi.spyOn(client, 'getPlayerStats').mockResolvedValue(PLAYERS)
  vi.spyOn(client, 'getTeamConsistency').mockResolvedValue({ own: vectors.leagues[0].consistency, rival: {} } as never)
  vi.spyOn(client, 'getShotRaw').mockResolvedValue([])
  vi.spyOn(client, 'getShotZones').mockResolvedValue([])
  return vi.spyOn(source, 'localLastMatch').mockResolvedValue({ team: TEAMS[0], opponent: TEAMS[1], opponentName: B, date: '03-11-2025' } as never)
}

describe('the weekly report', () => {
  it('on: it is made here, a zip of the tables with the progress of its five steps, and nothing is asked of the server', async () => {
    const lastMatch = browserData()
    const fetched = vi.spyOn(globalThis, 'fetch')
    const steps: number[] = []
    const blob = await downloadWeeklyReport(COLLECTION, '101', '102', p => steps.push(p.step))
    const files = unzipSync(new Uint8Array(await blob.arrayBuffer()))
    expect(Object.keys(files)).toEqual(expect.arrayContaining(['General/01_Basicas_Toda_Competicion.png', `General/05_Ultimo_Partido_${A}.png`, `${B}/1_Estadisticas_Individuales/02_${B}_Totales.png`]))
    expect(strFromU8(files['General/01_Basicas_Toda_Competicion.png'])).toContain('<svg')
    expect(steps).toEqual([1, 2, 3, 4, 5])
    expect(lastMatch).toHaveBeenCalledWith(COLLECTION, A)
    expect(fetched).not.toHaveBeenCalled()
  })

  it('on, asking the shots of a team and of each of its players for the charts', async () => {
    browserData()
    const shots = vi.spyOn(client, 'getShotRaw').mockImplementation(async (_c, p) => (p.player ? [] : [{ x: 7, y: 3, made: true, zone: 'key_area' }]))
    await downloadWeeklyReport(COLLECTION, '101', '102')
    expect(shots).toHaveBeenCalledWith(COLLECTION, expect.objectContaining({ team_id: '101' }))
    expect(shots).toHaveBeenCalledWith(COLLECTION, expect.objectContaining({ team_id: '101', player: 'p0' }))
  })

  it('on, with no key for the data: the reader must unlock, the report is not made half blank', async () => {
    browserData()
    vi.spyOn(client, 'getTeamStats').mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(downloadWeeklyReport(COLLECTION, '101', '102')).rejects.toBeInstanceOf(ScopedAccessError)
  })

  it('on, with a team that is not of the competition: it says so instead of making an empty report', async () => {
    browserData()
    await expect(downloadWeeklyReport(COLLECTION, '101', '999')).rejects.toThrow(/equipo/i)
  })

})
