import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getLineupAnalysis, LAST_GAME, streamLineupAnalysis } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadWebLineups, WebDataUnavailable } from '@/webdata/client'
import vectors from '../../../tests/local_vectors/lineups_feb.json'

// Issue #686: Combinaciones is its own dataset (`lineups`): on, the table of a team is merged on the device from the per-game counters of the publication (at once, no stream); off,
// or when the competition or the team is not published, the API.
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebLineups: vi.fn() }))

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const TEAM = vectors.team
let calls: string[]
let streamed: string[]
const realFetch = globalThis.fetch
const realEventSource = (globalThis as { EventSource?: unknown }).EventSource

class FakeEventSource {                                              // what the API answers when the stream is asked for
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  constructor(url: string) { streamed.push(url); setTimeout(() => this.onmessage?.({ data: JSON.stringify({ done: true, result: [{ players: ['DE LA API'] }] }) }), 0) }
  close() { /* nothing */ }
}

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []; streamed = []
  vi.mocked(loadWebLineups).mockReset().mockResolvedValue(vectors.published as never)
  ;(globalThis as { EventSource?: unknown }).EventSource = FakeEventSource
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    return { ok: true, json: async () => [{ players: ['DE LA API'] }] }
  }) as unknown as typeof fetch
})
afterEach(() => { vi.useRealTimers(); globalThis.fetch = realFetch; (globalThis as { EventSource?: unknown }).EventSource = realEventSource })       // not unstubAllGlobals: it would drop the in-memory localStorage of the setup

describe('data source switch: Combinaciones', () => {
  it('off: the API answers, the stream is the stream of the API, and nothing is downloaded', async () => {
    expect((await getLineupAnalysis(COLLECTION, TEAM, 'A'))[0].players).toEqual(['DE LA API'])
    expect((await streamLineupAnalysis(COLLECTION, TEAM, 'A'))[0].players).toEqual(['DE LA API'])
    expect(loadWebLineups).not.toHaveBeenCalled()
  })

  it('on: the table is merged from the publication (one file for every size, period and statistic), at once and without the stream', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:lineups')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(`${vectors.now}Z`))                          // "the last 30 days" are counted from the day of the vectors
    const progress = vi.fn()
    const free = await streamLineupAnalysis(COLLECTION, TEAM, 'A', 5, 'net_rating', 0, false, 0, 0, progress)
    const expected = vectors.cases.find(c => c.config.name === 'no minimums' && c.size === 5)!.rows
    expect(free).toHaveLength(expected.length)
    expect(progress).toHaveBeenCalledWith(100, 1, 1)
    expect(await getLineupAnalysis(COLLECTION, TEAM, 'A', 3, 'drtg', 30, true, 0, 0)).not.toHaveLength(0)
    expect(streamed).toEqual([])
    expect(calls).toEqual([])
    expect(loadWebLineups).toHaveBeenCalledTimes(1)
  })

  it('"Último partido" is the last game, not a period of -1 days', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:lineups')
    const last = await getLineupAnalysis(COLLECTION, TEAM, 'A', 3, 'net_rating', LAST_GAME, false, 0, 0)
    const expected = vectors.cases.find(c => c.config.name === 'the last game')!.rows
    expect(last).toHaveLength(expected.length)
    expect(last.every(row => row.games_played === 1)).toBe(true)
  })

  it('on, but the team is not in the publication or the competition is not published: the API; with no key: the access error, not the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:lineups')
    expect((await streamLineupAnalysis(COLLECTION, 'NOBODY', 'X'))[0].players).toEqual(['DE LA API'])
    resetLocalData()
    vi.mocked(loadWebLineups).mockRejectedValue(new WebDataUnavailable('no publicado'))
    expect((await getLineupAnalysis(COLLECTION, TEAM, 'A'))[0].players).toEqual(['DE LA API'])
    resetLocalData()
    vi.mocked(loadWebLineups).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(streamLineupAnalysis(COLLECTION, TEAM, 'A')).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
