import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { DATA_FLAG_KEY, localDataEnabled, localPlayerStats, localTeamStats, resetLocalData } from './source'
import { loadWebRows, WebDataUnavailable } from '@/webdata/client'
import teams from '../../../tests/local_vectors/team_stats_feb.json'
import players from '../../../tests/local_vectors/players_feb.json'
import fbcylTeams from '../../../tests/local_vectors/team_stats_fbcyl.json'
import fbcylPlayers from '../../../tests/local_vectors/players_fbcyl.json'

// The published rows come from `webdata/client`; here they are not published unless a test says so (the manual export `local-data/` is the fallback).
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), loadWebRows: vi.fn() }))

// The local data source (issue #327, step 2): the web reads the exported files instead of the API when `?data=local` is on, and says so
// (null) whenever it cannot answer, so that the caller falls back to the API instead of showing an empty table.
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FBCYL = 'FBCYL_1ª_FASE-GRUPO_A-1_2026_'
const INDEX = { format: 1, collections: [{ name: FEB, file: 'feb.json', league: 'feb', games: 12, bytes: 1 }, { name: FBCYL, file: 'fb.json', league: 'fbcyl', games: 12, bytes: 1 }] }
const FILES: Record<string, unknown> = {
  'index.json': INDEX,
  'feb.json': { format: 1, collection: FEB, league: 'feb', games: 12, team_rows: teams.rows, player_rows: players.rows },
  'fb.json': { format: 1, collection: FBCYL, league: 'fbcyl', games: 12, team_rows: fbcylTeams.rows, player_rows: fbcylPlayers.rows },
}

let fetched: string[]
function serve(files: Record<string, unknown> = FILES) {
  fetched = []
  globalThis.fetch = vi.fn(async (url: string) => {
    const name = String(url).split('/').pop() as string
    fetched.push(name)
    return name in files ? { ok: true, json: async () => files[name] } : { ok: false, status: 404, json: async () => ({}) }
  }) as unknown as typeof fetch
}
const turnOn = () => localStorage.setItem(DATA_FLAG_KEY, 'local')

beforeEach(() => {
  localStorage.clear(); resetLocalData(); window.history.replaceState(null, '', '/')
  vi.mocked(loadWebRows).mockReset().mockRejectedValue(new WebDataUnavailable('no publicado'))
})
const realFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = realFetch })          // not unstubAllGlobals: it would drop the in-memory localStorage of the setup

describe('the switch', () => {
  it('is off by default, and nothing is fetched', async () => {
    serve()
    expect(localDataEnabled()).toBe(false)
    expect(await localTeamStats(FEB, {})).toBeNull()
    expect(fetched).toEqual([])
  })

  it('?data=local turns it on and the choice is remembered; ?data=api turns it off', () => {
    window.history.replaceState(null, '', '/x?data=local')
    expect(localDataEnabled()).toBe(true)
    window.history.replaceState(null, '', '/y')
    expect(localDataEnabled()).toBe(true)
    window.history.replaceState(null, '', '/y?data=api')
    expect(localDataEnabled()).toBe(false)
    expect(localStorage.getItem(DATA_FLAG_KEY)).toBeNull()
  })
})

describe('local tables', () => {
  it('team tables are the aggregation of the exported rows with the filters', async () => {
    serve(); turnOn()
    const all = await localTeamStats(FEB, {})
    expect(all?.team_stats.reduce((n, t) => n + t.total_games, 0)).toBe(24)
    const home = await localTeamStats(FEB, { venue: 'home' })
    expect(home?.team_stats.reduce((n, t) => n + t.total_games, 0)).toBe(12)
  })

  it('player tables come from the player rows, with the team filter', async () => {
    serve(); turnOn()
    const one = await localPlayerStats(FEB, { team: 'BRAVO' })
    expect(new Set(one?.map(p => p.team_name))).toEqual(new Set(['BRAVO']))
  })

  it('the files are fetched once per competition however many tables are asked', async () => {
    serve(); turnOn()
    await Promise.all([localTeamStats(FEB, {}), localTeamStats(FEB, { venue: 'away' }), localPlayerStats(FEB, {})])
    expect(fetched.filter(n => n === 'feb.json')).toHaveLength(1)
    expect(fetched.filter(n => n === 'index.json')).toHaveLength(1)
  })

  it('answers null (use the API) for a competition that is not exported', async () => {
    serve(); turnOn()
    expect(await localTeamStats('L_F_-2_2025_2026_Nope', {})).toBeNull()
  })

  it('the players of FBCYL are summed with the FBCYL table, not the FEB one (#644)', async () => {
    serve(); turnOn()
    const table = (await localPlayerStats(FBCYL, {})) as unknown as Array<Record<string, number | string>>
    expect(table.length).toBeGreaterThan(0)
    expect(table.every(p => p.player_uuid && p.total_minutes === Number(p.minutes_per_game) * Number(p.games_played))).toBe(true)   // whole minutes, not seconds / 60
    const one = await localPlayerStats(FBCYL, { team: 'BRAVO' })
    expect(one?.length).toBeGreaterThan(0)
    expect(one?.every(p => p.team_name === 'BRAVO')).toBe(true)
  })

  it('an FBCYL competition exported before the player rows existed (null) still falls back to the API for its players', async () => {
    serve({ ...FILES, 'fb.json': { format: 1, collection: FBCYL, league: 'fbcyl', games: 0, team_rows: [], player_rows: null } }); turnOn()
    expect(await localPlayerStats(FBCYL, {})).toBeNull()
    expect(await localTeamStats(FBCYL, {})).toEqual({ team_stats: [], opponent_stats: [] })
  })

  it('answers null when the files cannot be fetched, and tries again next time (a failed load is not cached)', async () => {
    serve({}); turnOn()
    expect(await localTeamStats(FEB, {})).toBeNull()
    serve()
    expect(await localTeamStats(FEB, {})).not.toBeNull()
  })

  it('answers null for a file of another format version', async () => {
    serve({ ...FILES, 'index.json': { ...INDEX, format: 99 } }); turnOn()
    expect(await localTeamStats(FEB, {})).toBeNull()
  })
})

// Issue #673 (P4): the rows of the publication (`rows/` of web-data) are what the tables are computed from; the manual export is the fallback of development.
describe('the rows of the publication', () => {
  it('are used first: the tables are computed from them and the manual export is not even asked for', async () => {
    serve(); turnOn()
    vi.mocked(loadWebRows).mockResolvedValue({ format: 1, collection: FEB, league: 'feb', games: 12, team_rows: teams.rows, player_rows: players.rows } as never)
    const all = await localTeamStats(FEB, {})
    expect(all?.team_stats.reduce((n, t) => n + t.total_games, 0)).toBe(24)
    expect(await localPlayerStats(FEB, { team: 'BRAVO' })).not.toBeNull()
    expect(loadWebRows).toHaveBeenCalledTimes(1)                   // once per competition for the team and the player tables
    expect(fetched).toEqual([])
  })

  it('a competition that is not published falls back to the manual export, and then to the API (null)', async () => {
    serve(); turnOn()
    expect((await localTeamStats(FEB, {}))?.team_stats.length).toBeGreaterThan(0)
    resetLocalData()
    serve({})
    expect(await localTeamStats(FEB, {})).toBeNull()
  })

  it('a reader without the key is told so (the access error goes through), not sent to the API', async () => {
    serve(); turnOn()
    vi.mocked(loadWebRows).mockRejectedValue(new ScopedAccessError('sin clave'))
    await expect(localTeamStats(FEB, {})).rejects.toBeInstanceOf(ScopedAccessError)
  })

  it('rows of another format are not used', async () => {
    serve({}); turnOn()
    vi.mocked(loadWebRows).mockResolvedValue({ format: 99, collection: FEB, league: 'feb', games: 1, team_rows: [], player_rows: null } as never)
    expect(await localTeamStats(FEB, {})).toBeNull()
  })
})
