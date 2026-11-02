import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getTeamEvolution } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import teams from '../../../tests/local_vectors/team_stats_feb.json'
import evolution from '../../../tests/local_vectors/team_evolution_feb.json'

// Issue #708: the evolution of a team (dataset `evolution`, the one of the competition's) is computed from the rows; off, with a window the API refuses (2 to 15) or an unpublished competition, the API.
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FILES: Record<string, unknown> = {
  'index.json': { format: 1, collections: [{ name: FEB, file: 'feb.json', league: 'feb', games: 12, bytes: 1 }] },
  'feb.json': { format: 1, collection: FEB, league: 'feb', games: 12, team_rows: teams.rows, player_rows: null },
}
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    const file = String(url).split('/local-data/')[1]
    if (file) return file in FILES ? { ok: true, json: async () => FILES[file] } : { ok: false, json: async () => ({}) }
    return { ok: true, json: async () => [{ game_number: -1 }] }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: the evolution of a team', () => {
  const want = evolution.cases.find(c => c.team_id === '101' && c.stat === 'points' && c.window === 5)!.points

  it('off: the API answers', async () => {
    expect((await getTeamEvolution(FEB, '101', 'points', 5))[0].game_number).toBe(-1)
  })

  it('on: the series of the rows, the one of the API, with no call to it', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:evolution')
    expect(await getTeamEvolution(FEB, '101', 'points', 5)).toEqual(want)
    expect(calls.filter(c => c.includes('/api/'))).toEqual([])
  })

  it('on with a window the API refuses, or a competition that is not published: the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:evolution')
    expect((await getTeamEvolution(FEB, '101', 'points', 20))[0].game_number).toBe(-1)
    expect((await getTeamEvolution('OTRA', '101', 'points', 5))[0].game_number).toBe(-1)
  })
})
