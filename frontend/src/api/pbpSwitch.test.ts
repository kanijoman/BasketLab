import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getByPeriod, getDerivedCoverage, getPointsByOrigin, getSituations, getTimeoutEffects } from './pbpExtended'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebDerived, WebDataUnavailable } from '@/webdata/client'
import vectors from '../../../tests/local_vectors/pbp_feb.json'

// Issue #676: Análisis PBP is its own dataset (`pbp`): on, the five tables are summed on the device from the published DERIVED; off, or when it is not published, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebDerived: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  vi.mocked(loadWebDerived).mockReset().mockResolvedValue(vectors.derived as never)
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    return { ok: true, json: async () => [{ team_name: 'DE LA API' }] }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: Análisis PBP', () => {
  it('off: the API answers every table and nothing local is read', async () => {
    expect((await getPointsByOrigin(COLLECTION))[0].team_name).toBe('DE LA API')
    expect((await getByPeriod(COLLECTION))[0].team_name).toBe('DE LA API')
    expect((await getSituations(COLLECTION))[0].team_name).toBe('DE LA API')
    expect((await getTimeoutEffects(COLLECTION))[0].team_name).toBe('DE LA API')
    expect(loadWebDerived).not.toHaveBeenCalled()
  })

  it('on: the five tables are what the services answer, summed on the device, and the API is not asked', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:pbp')
    expect((await getPointsByOrigin(COLLECTION)).map(r => r.team_name)).toEqual(vectors.expected.origin.map(r => r.team_name))
    expect((await getByPeriod(COLLECTION)).map(r => r.team_name)).toEqual(vectors.expected.periods.map(r => r.team_name))
    expect((await getSituations(COLLECTION)).map(r => r.team_name)).toEqual(vectors.expected.situations.map(r => r.team_name))
    expect((await getTimeoutEffects(COLLECTION)).map(r => r.team_name)).toEqual(vectors.expected.timeouts.map(r => r.team_name))
    expect((await getDerivedCoverage(COLLECTION)).pending).toBe(vectors.expected.coverage.pending)
    expect(calls).toEqual([])
    expect(loadWebDerived).toHaveBeenCalledTimes(1)                         // one file per competition for the five tables
  })

  it('on, but the competition has no published DERIVED: the API answers', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:pbp')
    vi.mocked(loadWebDerived).mockRejectedValue(new WebDataUnavailable('no publicado'))
    expect((await getSituations(COLLECTION))[0].team_name).toBe('DE LA API')
  })

  it('on, but the reader has no key: the access error goes through, the API is not a way round it', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:pbp')
    vi.mocked(loadWebDerived).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getByPeriod(COLLECTION)).rejects.toBeInstanceOf(ScopedAccessError)
    expect(calls).toEqual([])
  })

  it('only that dataset reads the published DERIVED: the others keep reading the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:team-comparison')
    expect((await getPointsByOrigin(COLLECTION))[0].team_name).toBe('DE LA API')
  })
})
