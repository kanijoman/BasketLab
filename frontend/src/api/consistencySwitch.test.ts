import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getPlayerConsistency } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebConsistency, WebDataUnavailable } from '@/webdata/client'
import { DataUnavailable } from '@/datasource/resolve'

// Issue #709: the consistency of the players is its own dataset (`player-consistency`): on, the answer of the endpoint computed when the competition was published; off, or when it
// is not published, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebConsistency: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const MAP = { '9': { points_per_game: { mean: 10.5, std: 2, cv: 19, n: 5 } } }
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); localStorage.setItem('basketlab.data', 'api'); resetLocalData(); calls = []
  vi.mocked(loadWebConsistency).mockReset().mockResolvedValue({ format: 1, collection: COLLECTION, league: 'feb', players: MAP } as never)
  globalThis.fetch = vi.fn(async (url: string) => { calls.push(String(url)); return { ok: true, json: async () => ({ DE_LA_API: {} }) } }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: the consistency of the players', () => {
  it('off: the API answers', async () => {
    expect(await getPlayerConsistency(COLLECTION)).toEqual({ DE_LA_API: {} })
    expect(loadWebConsistency).not.toHaveBeenCalled()
  })

  it('on: the published answer, once per competition, with no call to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:player-consistency')
    expect(await getPlayerConsistency(COLLECTION)).toEqual(MAP)
    expect(await getPlayerConsistency(COLLECTION)).toEqual(MAP)
    expect(calls).toEqual([])
    expect(loadWebConsistency).toHaveBeenCalledTimes(1)
  })

  it('on but not published: a clear error, not the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:player-consistency')
    vi.mocked(loadWebConsistency).mockRejectedValue(new WebDataUnavailable('sin fichero'))
    await expect(getPlayerConsistency(COLLECTION)).rejects.toBeInstanceOf(DataUnavailable)
  })

  it('on without the key: the access error, never the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:player-consistency')
    vi.mocked(loadWebConsistency).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getPlayerConsistency(COLLECTION)).rejects.toBeInstanceOf(ScopedAccessError)
    expect(calls).toEqual([])
  })
})
