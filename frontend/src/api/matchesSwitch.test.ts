import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getMatchAnalysis, getMatchList } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebMatches, WebDataUnavailable } from '@/webdata/client'

// Issue #677: Partidos is its own dataset (`matches`): on, the list and the analysis of a match are the ones computed when the competition was published; off, or when
// they are not published (or the match is not in them), the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebMatches: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const ANALYSIS = { home: { team_name: 'ALPHA' }, away: { team_name: 'BRAVO' }, comparison: [{ stat_key: 'pts' }] }
const PUBLISHED = {
  format: 1, collection: COLLECTION, league: 'feb', games: 2,
  matches: [
    { match_id: 9001, date: '03-10-2025 - 18:00', round: '1', venue: 'A', home_team: 'ALPHA', away_team: 'BRAVO', home_score: 80, away_score: 70, analysis: ANALYSIS },
    { match_id: 9002, date: '10-10-2025 - 18:00', round: '2', venue: 'B', home_team: 'BRAVO', away_team: 'ALPHA', home_score: 60, away_score: 61, analysis: null },
  ],
}
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  vi.mocked(loadWebMatches).mockReset().mockResolvedValue(PUBLISHED as never)
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    return { ok: true, json: async () => (String(url).includes('/matches/') && /\/\d+\?/.test(String(url)) ? { home: { team_name: 'DE LA API' }, away: {}, comparison: [] } : [{ match_id: -1 }]) }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: Partidos', () => {
  it('off: the API answers the list and the analysis', async () => {
    expect((await getMatchList(COLLECTION))[0].match_id).toBe(-1)
    expect((await getMatchAnalysis(COLLECTION, 9001)).home.team_name).toBe('DE LA API')
    expect(loadWebMatches).not.toHaveBeenCalled()
  })

  it('on: the list has no analyses in it, the analysis of a match is the published one, with one file for both and no call to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:matches')
    const list = await getMatchList(COLLECTION)
    expect(list.map(m => m.match_id)).toEqual([9001, 9002])
    expect(list[0]).not.toHaveProperty('analysis')
    expect(await getMatchAnalysis(COLLECTION, 9001)).toEqual(ANALYSIS)
    expect(await getMatchAnalysis(COLLECTION, '9001')).toEqual(ANALYSIS)                // the id of the page may be text (FBCYL) or a number (FEB)
    expect(calls).toEqual([])
    expect(loadWebMatches).toHaveBeenCalledTimes(1)
  })

  it('on, but the match has no analysis in the publication or is not there: the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:matches')
    expect((await getMatchAnalysis(COLLECTION, 9002)).home.team_name).toBe('DE LA API')
    expect((await getMatchAnalysis(COLLECTION, 424242)).home.team_name).toBe('DE LA API')
  })

  it('on, but not published: the API; with no key: the access error, not the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:matches')
    vi.mocked(loadWebMatches).mockRejectedValue(new WebDataUnavailable('no publicado'))
    expect((await getMatchList(COLLECTION))[0].match_id).toBe(-1)
    resetLocalData()
    vi.mocked(loadWebMatches).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getMatchList(COLLECTION)).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
