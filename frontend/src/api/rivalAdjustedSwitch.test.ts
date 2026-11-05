import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getRivalAdjusted } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebRivalAdjusted, WebDataUnavailable } from '@/webdata/client'

// Issue #710: the rival-adjusted figures are their own dataset (`rival-adjusted`): on, the answer of the endpoint computed when the competition was published; off, or when it
// is not published, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebRivalAdjusted: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const MAP = { ALPHA: { ortg: { raw_avg: 100, adj_avg: 101.5, adj: 1.5, sos: 99, n: 6 } } }
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); localStorage.setItem('basketlab.data', 'api'); resetLocalData(); calls = []
  vi.mocked(loadWebRivalAdjusted).mockReset().mockResolvedValue({ format: 1, collection: COLLECTION, league: 'feb', teams: MAP } as never)
  globalThis.fetch = vi.fn(async (url: string) => { calls.push(String(url)); return { ok: true, json: async () => ({ DE_LA_API: {} }) } }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: the rival-adjusted figures', () => {
  it('off: the API answers', async () => {
    expect(await getRivalAdjusted(COLLECTION)).toEqual({ DE_LA_API: {} })
    expect(loadWebRivalAdjusted).not.toHaveBeenCalled()
  })

  it('on: the published answer, once per competition, with no call to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:rival-adjusted')
    expect(await getRivalAdjusted(COLLECTION)).toEqual(MAP)
    expect(await getRivalAdjusted(COLLECTION)).toEqual(MAP)
    expect(calls).toEqual([])
    expect(loadWebRivalAdjusted).toHaveBeenCalledTimes(1)
  })

  it('on but not published: the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:rival-adjusted')
    vi.mocked(loadWebRivalAdjusted).mockRejectedValue(new WebDataUnavailable('sin fichero'))
    expect(await getRivalAdjusted(COLLECTION)).toEqual({ DE_LA_API: {} })
  })

  it('on without the key: the access error, never the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:rival-adjusted')
    vi.mocked(loadWebRivalAdjusted).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getRivalAdjusted(COLLECTION)).rejects.toBeInstanceOf(ScopedAccessError)
    expect(calls).toEqual([])
  })
})
