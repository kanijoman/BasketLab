import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { fetchPossessionQualityCsv, fetchPossessionsCsv, getPossessionStats, getTeamConsistency } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebPossessionCsv, loadWebPossessions, WebDataUnavailable } from '@/webdata/client'

// Issue #679: Posesiones is its own dataset (`possessions`): on, the table, the consistency and the two CSV files are the ones computed when the competition was published (the
// downloads are made in the browser, with the BOM Excel needs once at their start); off, or when they are not published, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebPossessions: vi.fn(), loadWebPossessionCsv: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const TABLE = [{ team_name: 'ALPHA', pace: 70.5 }]
const CONSISTENCY = { own: { ALPHA: { points: { mean: 80, std: 5, cv: 6.2, n: 2 } } }, rival: {} }
const POSSESSIONS = { format: 1, collection: COLLECTION, league: 'feb', table: TABLE, consistency: CONSISTENCY, quality_csv: 'ID_Partido,Equipo\n1,A\n' }
const CSV = { format: 1, collection: COLLECTION, league: 'feb', games: 1, csv: 'ID_Partido,Equipo\n1,A\n' }
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  vi.mocked(loadWebPossessions).mockReset().mockResolvedValue(POSSESSIONS as never)
  vi.mocked(loadWebPossessionCsv).mockReset().mockResolvedValue(CSV as never)
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    return { ok: true, json: async () => (String(url).includes('consistency') ? { own: { API: {} }, rival: {} } : [{ team_name: 'DE LA API' }]), blob: async () => new Blob(['de la api']) }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

const text = async (blob: Blob) => new TextDecoder('utf-8', { ignoreBOM: true }).decode(await blob.arrayBuffer())       // keep the BOM: it is what is checked

describe('data source switch: Posesiones', () => {
  it('off: the API answers the table, the consistency and the downloads', async () => {
    expect((await getPossessionStats(COLLECTION))[0].team_name).toBe('DE LA API')
    expect(Object.keys((await getTeamConsistency(COLLECTION)).own)).toEqual(['API'])
    expect(await text(await fetchPossessionsCsv(COLLECTION))).toBe('de la api')
    expect(loadWebPossessions).not.toHaveBeenCalled()
  })

  it('on: the table and the consistency are the published ones, from one file, with no call to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:possessions')
    expect(await getPossessionStats(COLLECTION)).toEqual(TABLE)
    expect((await getTeamConsistency(COLLECTION)).own).toEqual(CONSISTENCY.own)
    expect(calls).toEqual([])
    expect(loadWebPossessions).toHaveBeenCalledTimes(1)
  })

  it('on: the downloads are made here, with ONE BOM at the start and the text as it was published; the heavy CSV is read only when it is asked for', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:possessions')
    expect(loadWebPossessionCsv).not.toHaveBeenCalled()
    const rows = await fetchPossessionsCsv(COLLECTION)
    expect(rows.type).toContain('text/csv')
    const bytes = new Uint8Array(await rows.arrayBuffer())
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf])
    expect(await text(rows)).toBe('\ufeffID_Partido,Equipo\n1,A\n')
    expect(await text(await fetchPossessionQualityCsv(COLLECTION))).toBe('\ufeffID_Partido,Equipo\n1,A\n')
    expect(calls).toEqual([])
  })

  it('on, but not published: the API (also for the downloads); with no key: the access error', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:possessions')
    vi.mocked(loadWebPossessions).mockRejectedValue(new WebDataUnavailable('no publicado'))
    vi.mocked(loadWebPossessionCsv).mockRejectedValue(new WebDataUnavailable('no publicado'))
    expect((await getPossessionStats(COLLECTION))[0].team_name).toBe('DE LA API')
    expect(await text(await fetchPossessionsCsv(COLLECTION))).toBe('de la api')
    resetLocalData()
    vi.mocked(loadWebPossessions).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getTeamConsistency(COLLECTION)).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
