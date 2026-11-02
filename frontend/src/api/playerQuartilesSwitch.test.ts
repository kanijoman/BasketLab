import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getPlayerQuartiles } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import teams from '../../../tests/local_vectors/team_stats_feb.json'
import players from '../../../tests/local_vectors/players_feb.json'
import quartiles from '../../../tests/local_vectors/player_quartiles.json'

// Issue #707: the quartiles of the players are computed from the player table of the competition (dataset `player-stats`); off, or when the competition is not published, the API.
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FILES: Record<string, unknown> = {
  'index.json': { format: 1, collections: [{ name: FEB, file: 'feb.json', league: 'feb', games: 12, bytes: 1 }] },
  'feb.json': { format: 1, collection: FEB, league: 'feb', games: 12, team_rows: teams.rows, player_rows: players.rows },
}
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    const file = String(url).split('/local-data/')[1]
    if (file) return file in FILES ? { ok: true, json: async () => FILES[file] } : { ok: false, json: async () => ({}) }
    return { ok: true, json: async () => ({ points_per_game: { count: -1 } }) }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch: the quartiles of the players', () => {
  it('off: the API answers', async () => {
    expect((await getPlayerQuartiles(FEB)).points_per_game.count).toBe(-1)
  })

  it('on: the quartiles of the player table of the rows, the ones of the API, with no call to it', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:player-stats')
    expect(await getPlayerQuartiles(FEB)).toEqual(quartiles.feb.quartiles)
    expect(calls.filter(c => c.includes('/api/'))).toEqual([])
  })

  it('on but the competition is not published: the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:player-stats')
    expect((await getPlayerQuartiles('OTRA')).points_per_game.count).toBe(-1)
  })
})
