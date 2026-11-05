import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getCollectionList } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebCollectionInfos, WebDataUnavailable } from '@/webdata/client'

// Issue #705: the list of competitions is its own dataset (`collections`): on, it is the one of the manifest of the publication; off, or with no publication, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebCollectionInfos: vi.fn() }))

const MANIFEST = [
  { collection: 'PRIMERA_FEB_2025_2026_Liga_Regular_Único', league: 'feb', games: 306 },
  { collection: 'FBCYL_1ª_FASE-GRUPO_A-1_2026_', league: 'fbcyl', games: 12 },
]
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); localStorage.setItem('basketlab.data', 'api'); resetLocalData(); calls = []
  vi.mocked(loadWebCollectionInfos).mockReset().mockResolvedValue(MANIFEST as never)
  globalThis.fetch = vi.fn(async (url: string) => { calls.push(String(url)); return { ok: true, json: async () => [{ name: 'DE_LA_API' }] } }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: the list of competitions', () => {
  it('off: the API answers', async () => {
    expect((await getCollectionList())[0].name).toBe('DE_LA_API')
    expect(loadWebCollectionInfos).not.toHaveBeenCalled()
  })

  it('on: the manifest answers, sorted as the API sorts, and no call goes to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:collections')
    const list = await getCollectionList()
    expect(list.map(c => [c.name, c.league, c.game_count])).toEqual([['FBCYL_1ª_FASE-GRUPO_A-1_2026_', 'FBCYL', 12], ['PRIMERA_FEB_2025_2026_Liga_Regular_Único', 'FEB', 306]].sort((a, b) => String(a[1]).localeCompare(String(b[1]))))
    expect(calls).toEqual([])
  })

  it('on but nothing published: the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:collections')
    vi.mocked(loadWebCollectionInfos).mockRejectedValue(new WebDataUnavailable('sin publicación'))
    expect((await getCollectionList())[0].name).toBe('DE_LA_API')
  })

  it('on without the key: the access error, never the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:collections')
    vi.mocked(loadWebCollectionInfos).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getCollectionList()).rejects.toBeInstanceOf(ScopedAccessError)
    expect(calls).toEqual([])
  })
})
