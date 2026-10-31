import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getInOutAnalysis } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebInOut, WebDataUnavailable } from '@/webdata/client'

// Issue #678: IN/OUT is its own dataset (`inout`): on, the analysis of a FEB player is the one computed when the competition was published; off, FBCYL, an unpublished competition or a
// player that is not in it, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebInOut: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const ANALYSIS = { on: { minutes: 10 }, off: { minutes: 30 }, player_id: '7' }
const PUBLISHED = { format: 1, collection: COLLECTION, league: 'feb', players: [{ player_id: '7', analysis: ANALYSIS }, { player_id: '8', analysis: {} }] }
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  vi.mocked(loadWebInOut).mockReset().mockResolvedValue(PUBLISHED as never)
  globalThis.fetch = vi.fn(async (url: string) => { calls.push(String(url)); return { ok: true, json: async () => ({ on: { minutes: -1 } }) } }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })                       // not unstubAllGlobals: it would drop the in-memory localStorage of the setup

describe('data source switch: IN/OUT', () => {
  it('off: the API answers and nothing is downloaded', async () => {
    expect((await getInOutAnalysis(COLLECTION, '7')).on.minutes).toBe(-1)
    expect(loadWebInOut).not.toHaveBeenCalled()
  })

  it('on: the analysis as it was published, one file for every player, without calling the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:inout')
    expect(await getInOutAnalysis(COLLECTION, '7')).toEqual(ANALYSIS)
    expect(await getInOutAnalysis(COLLECTION, '8')).toEqual({})               // a player the endpoint cannot analyse: empty, as the endpoint says
    expect(calls).toEqual([])
    expect(loadWebInOut).toHaveBeenCalledTimes(1)
  })

  it('on, but the player is not in the publication or the competition is not published: the API; with no key: the access error, not the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:inout')
    expect((await getInOutAnalysis(COLLECTION, '999')).on.minutes).toBe(-1)
    resetLocalData()
    vi.mocked(loadWebInOut).mockRejectedValue(new WebDataUnavailable('no publicado'))
    expect((await getInOutAnalysis(COLLECTION, '7')).on.minutes).toBe(-1)
    resetLocalData()
    vi.mocked(loadWebInOut).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getInOutAnalysis(COLLECTION, '7')).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
