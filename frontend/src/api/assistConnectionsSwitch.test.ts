import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getAssistConnections } from './assistConnections'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebAssistConnections, WebDataUnavailable } from '@/webdata/client'
import { DataUnavailable } from '@/datasource/resolve'

// Issue #773: the assist connections are their own dataset (`assist-connections`): on, the analysis of the team is the one computed when the competition was published; off,
// the API. A team the publication does not have is a clear error, never the API in its place.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebAssistConnections: vi.fn() }))

const COLLECTION = 'LF_CHALLENGE_2026_2027_Liga_Regular_Único'
const ANALYSIS = { team_id: '101', games: 3, receivers: [], passers: [] }
const PUBLISHED = { format: 1, collection: COLLECTION, league: 'feb', teams: [{ team_id: '101', team_name: 'ALPHA', analysis: ANALYSIS }] }
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); localStorage.setItem(DATA_FLAG_KEY, 'api'); resetLocalData(); calls = []
  vi.mocked(loadWebAssistConnections).mockReset().mockResolvedValue(PUBLISHED as never)
  globalThis.fetch = vi.fn(async (url: string) => { calls.push(String(url)); return { ok: true, json: async () => ({ ...ANALYSIS, games: -1 }) } }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: assist connections', () => {
  it('off: the API answers and nothing is downloaded', async () => {
    expect((await getAssistConnections(COLLECTION, '101')).games).toBe(-1)
    expect(calls[0]).toContain('/assist-connections/')
    expect(loadWebAssistConnections).not.toHaveBeenCalled()
  })

  it('on: the analysis of the team is the published one, with no request to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:assist-connections')
    expect((await getAssistConnections(COLLECTION, '101')).games).toBe(3)
    expect(calls).toEqual([])
  })

  it('on, but the team is not in the publication: a clear error, not the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:assist-connections')
    await expect(getAssistConnections(COLLECTION, '999')).rejects.toBeInstanceOf(DataUnavailable)
    expect(calls).toEqual([])
  })

  it('on, but the competition is not published: a clear error', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:assist-connections')
    vi.mocked(loadWebAssistConnections).mockRejectedValue(new WebDataUnavailable('no publicado'))
    await expect(getAssistConnections(COLLECTION, '101')).rejects.toBeInstanceOf(DataUnavailable)
  })
})
