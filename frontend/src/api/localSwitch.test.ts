import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getPlayerStats, getTeamStats } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import teams from '../../../tests/local_vectors/team_stats_feb.json'
import players from '../../../tests/local_vectors/players_feb.json'

// Issue #327, step 2: with the local data source on, Estadísticas de equipo and Rankings read the exported files; with it off, or when the
// competition is not exported, they ask the API as before (the pages do not know the difference).
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FILES: Record<string, unknown> = {
  'index.json': { format: 1, collections: [{ name: FEB, file: 'feb.json', league: 'feb', games: 12, bytes: 1 }] },
  'feb.json': { format: 1, collection: FEB, league: 'feb', games: 12, team_rows: teams.rows, player_rows: players.rows },
}
const API_TEAMS = { team_stats: [{ team_name: 'DE LA API' }], opponent_stats: [] }
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    const file = String(url).split('/local-data/')[1]
    if (file) return file in FILES ? { ok: true, json: async () => FILES[file] } : { ok: false, json: async () => ({}) }
    return { ok: true, json: async () => (String(url).includes('/teams/') ? API_TEAMS : [{ player_name: 'DE LA API' }]) }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

describe('data source switch in the API client', () => {
  it('off: the API answers and no local file is read', async () => {
    expect((await getTeamStats(FEB)).team_stats[0].team_name).toBe('DE LA API')
    expect((await getPlayerStats(FEB))[0].player_name).toBe('DE LA API')
    expect(calls.some(c => c.includes('local-data'))).toBe(false)
  })

  it('on: both tables are computed from the files and the API is not asked', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    const teamTable = await getTeamStats(FEB, { venue: 'home' })
    expect(teamTable.team_stats.reduce((n, t) => n + t.total_games, 0)).toBe(12)
    expect((await getPlayerStats(FEB, { team: 'BRAVO' })).every(p => p.team_name === 'BRAVO')).toBe(true)
    expect(calls.some(c => c.includes('/api/v1'))).toBe(false)
  })

  it('on but the competition is not exported: falls back to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    expect((await getTeamStats('L_F_-2_2025_2026_Otra')).team_stats[0].team_name).toBe('DE LA API')
  })
})
