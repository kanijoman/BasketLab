import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getLiveTeamNames, getTeamsInCollection } from './client'
import { DATA_FLAG_KEY, resetLocalData } from '@/localdata/source'
import { loadReportTeams, WebDataUnavailable } from '@/webdata/client'
import teams from '../../../tests/local_vectors/team_stats_feb.json'
import players from '../../../tests/local_vectors/players_feb.json'

// Issue #706: the teams of a competition without the API. `getLiveTeamNames` (`{id, name}`, deduplicated by id) is the team list of the report index (`report-teams`); `getTeamsInCollection`
// (the names, as `distinct` lists them) is the set of team names of the rows of the competition (`team-stats`).
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadReportTeams: vi.fn() }))

const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FILES: Record<string, unknown> = {
  'index.json': { format: 1, collections: [{ name: FEB, file: 'feb.json', league: 'feb', games: 12, bytes: 1 }] },
  'feb.json': { format: 1, collection: FEB, league: 'feb', games: 12, team_rows: teams.rows, player_rows: players.rows },
}
let calls: string[]
const realFetch = globalThis.fetch

beforeEach(() => {
  localStorage.clear(); resetLocalData(); calls = []
  vi.mocked(loadReportTeams).mockReset().mockResolvedValue([{ id: '101', name: 'ALPHA' }, { id: '102', name: 'BRAVO' }])
  globalThis.fetch = vi.fn(async (url: string) => {
    calls.push(String(url))
    const file = String(url).split('/local-data/')[1]
    if (file) return file in FILES ? { ok: true, json: async () => FILES[file] } : { ok: false, json: async () => ({}) }
    return { ok: true, json: async () => (String(url).includes('/teams/') ? [{ id: '0', name: 'DE LA API' }] : ['DE LA API']) }
  }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch })

const NAMES = [...new Set((teams.rows as Array<{ team_name: string }>).map(r => r.team_name))].sort()

describe('data source switch: the teams of a competition', () => {
  it('off: the API answers both', async () => {
    expect(await getLiveTeamNames(FEB)).toEqual([{ id: '0', name: 'DE LA API' }])
    expect(await getTeamsInCollection(FEB)).toEqual(['DE LA API'])
    expect(loadReportTeams).not.toHaveBeenCalled()
  })

  it('on: the list with ids is the one of the report index and the names are the ones of the rows, sorted, with no call to the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:report-teams,team-stats')
    expect(await getLiveTeamNames(FEB)).toEqual([{ id: '101', name: 'ALPHA' }, { id: '102', name: 'BRAVO' }])
    expect(await getTeamsInCollection(FEB)).toEqual(NAMES)
    expect(NAMES.length).toBeGreaterThan(1)
    expect(calls.filter(c => c.includes('/api/'))).toEqual([])
  })

  it('on but the competition is not published: the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:report-teams,team-stats')
    vi.mocked(loadReportTeams).mockRejectedValue(new WebDataUnavailable('sin informes'))
    expect(await getLiveTeamNames('OTRA')).toEqual([{ id: '0', name: 'DE LA API' }])
    expect(await getTeamsInCollection('OTRA')).toEqual(['DE LA API'])
  })

  it('on without the key: the access error, never the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:report-teams')
    vi.mocked(loadReportTeams).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(getLiveTeamNames(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
