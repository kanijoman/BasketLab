import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getShotRaw, getShotZones, streamRotacionesAnalysis } from './client'
import { resetLocalData } from '@/localdata/source'
import { loadWebRotations, loadWebShots, WebDataUnavailable } from '@/webdata/client'
import shotVectors from '../../../tests/local_vectors/shots_feb.json'
import { DataUnavailable } from '@/datasource/resolve'

// Issues #684 and #685: Tiros and Rotaciones are their own datasets (`shots`, `rotations`): on, the zones and the raw shots are counted on the device from the published
// shots and the analysis of a team is the one computed when the competition was published; off, or when it is not published, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebShots: vi.fn(), loadWebRotations: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const ANALYSIS = { total_games: 6, games_with_playbyplay: 6, players: [] }
const ROTATIONS = { format: 1, collection: COLLECTION, league: 'feb', teams: [{ team_id: '101', team_name: 'ALPHA', analysis: ANALYSIS }] }
let calls: string[]
let streamed: string[]
const realFetch = globalThis.fetch
const realEventSource = (globalThis as { EventSource?: unknown }).EventSource

class FakeEventSource {                                              // what the API answers when the stream is asked for
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  constructor(url: string) { streamed.push(url); setTimeout(() => this.onmessage?.({ data: JSON.stringify({ done: true, result: { total_games: -1 } }) }), 0) }
  close() { /* nothing */ }
}

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []; streamed = []
  vi.mocked(loadWebShots).mockReset().mockResolvedValue(shotVectors.payload as never)
  vi.mocked(loadWebRotations).mockReset().mockResolvedValue(ROTATIONS as never)
  ;(globalThis as { EventSource?: unknown }).EventSource = FakeEventSource
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    return { ok: true, json: async () => [{ zone: 'DE LA API', x: -1 }] }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch; (globalThis as { EventSource?: unknown }).EventSource = realEventSource })       // not unstubAllGlobals: it would drop the in-memory localStorage of the setup

describe('data source switch: Tiros', () => {
  it('on: the zones and the raw shots are what the endpoints answer, counted on the device, with one file for both', async () => {
    const zones = await getShotZones(COLLECTION, { compare: 'league' })
    expect(zones.map(z => z.zone)).toEqual(shotVectors.zones.find(c => c.compare === 'league' && Object.keys(c.filter).length === 0)!.zones.map(z => z.zone))
    const raw = await getShotRaw(COLLECTION, { limit: 7 })
    expect(raw).toHaveLength(7)
    expect(calls).toEqual([])
    expect(loadWebShots).toHaveBeenCalledTimes(1)
  })

  it('on, but not published: a clear error, not the API; with no key: the access error', async () => {
    vi.mocked(loadWebShots).mockRejectedValue(new WebDataUnavailable('no publicado'))
    await expect(getShotZones(COLLECTION, {})).rejects.toBeInstanceOf(DataUnavailable)
    resetLocalData()
    vi.mocked(loadWebShots).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getShotRaw(COLLECTION, {})).rejects.toBeInstanceOf(ScopedAccessError)
  })
})

describe('data source switch: Rotaciones', () => {
  it('on, but the team is not in the publication or the competition is not published: a clear error, not the API', async () => {
    await expect(streamRotacionesAnalysis(COLLECTION, '999')).rejects.toBeInstanceOf(DataUnavailable)
    resetLocalData()
    vi.mocked(loadWebRotations).mockRejectedValue(new WebDataUnavailable('no publicado'))
    await expect(streamRotacionesAnalysis(COLLECTION, '101')).rejects.toBeInstanceOf(DataUnavailable)
  })
})
