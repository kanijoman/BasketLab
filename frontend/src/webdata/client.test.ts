import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { ScopedAccessError } from '@live-package/crypto'
import { addRight, parseInvite, type Right } from '@live-package/rights'
import { loadReportTeams, loadScoutingScopes, loadWebReport, loadWebDerived, loadWebInOut, loadWebLineups, loadWebMatches, loadWebPossessionCsv, loadWebPossessions, loadWebRotations, loadWebRows, loadWebScouting, loadWebShots, resetWebData, setDataBase, WebDataUnavailable } from './client'

// The browser side of `web-data` (issues #328, #639), tested against a REAL publication of the exporter (`tests/local_vectors/web_data`, made by
// `generate_web_data.py`): sealed rows and reports, the manifest with the open key of the beta, the index of the reports of each competition.
const DIR = join(__dirname, '../../../tests/local_vectors/web_data')
const BASE = 'https://data.test/'
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FBCYL = 'FBCYL_1ª_FASE-GRUPO_A-1_2026_'
const MASTER = 'vector-master-secret-for-the-web-tests'

const read = (file: string) => readFileSync(join(DIR, file), 'utf-8')
let requested: string[]
let override: Record<string, string | null>

/** The host: the files of the publication; `override` swaps or removes some (a manifest without the open key, a file that has gone). */
function serve() {
  requested = []
  globalThis.fetch = vi.fn(async (input: string | URL | Request) => {
    const file = String(input).replace(BASE, '')
    requested.push(file)
    const body = file in override ? override[file] : read(file)
    return body === null
      ? { ok: false, status: 404, text: async () => '', json: async () => ({}) }
      : { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  }) as unknown as typeof fetch
}

/** The key of a scope, derived from the master as `package_scopes.scope_key` does (HKDF-SHA256, salt `basketlab-live-scopes-v1`). */
async function scopeKey(scope: string): Promise<Uint8Array> {
  const subtle = globalThis.crypto.subtle
  const material = await subtle.importKey('raw', new TextEncoder().encode(MASTER), 'HKDF', false, ['deriveBits'])
  const bits = await subtle.deriveBits(
    { name: 'HKDF', hash: 'SHA-256', salt: new TextEncoder().encode('basketlab-live-scopes-v1'), info: new TextEncoder().encode(scope) }, material, 256)
  return new Uint8Array(bits)
}

const b64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes))
const b64url = (bytes: Uint8Array) => b64(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
async function invitation(scope: string): Promise<Right> {
  const payload = JSON.stringify({ s: scope, k: b64(await scopeKey(scope)), e: null })
  return parseInvite(`bl1.${b64url(new TextEncoder().encode(payload))}`)
}
const withoutOpenKey = () => {
  const manifest = JSON.parse(read('index.json'))
  delete manifest.open_key
  override['index.json'] = JSON.stringify(manifest)
}

beforeEach(() => { localStorage.clear(); resetWebData(); setDataBase(BASE); override = {}; serve() })
afterEach(() => { vi.restoreAllMocks() })

describe('the reports of web-data, opened in the browser', () => {
  it('opens a sealed own-team report with the open key the manifest publishes (beta), as the exporter wrote it', async () => {
    const report = await loadWebReport(FEB, '101', 'own')
    expect(report.team).toBe('ALPHA')
    expect(report.mode).toBe('own')
    expect(report.games_played).toBeGreaterThan(0)
    expect(Array.isArray(report.strengths) && Array.isArray(report.tactics)).toBe(true)
  })

  it('opens the FBCYL reports too, own and rival', async () => {
    expect((await loadWebReport(FBCYL, '34001', 'own')).team).toBe('ALFA')
    expect((await loadWebReport(FBCYL, '34002', 'rival')).mode).toBe('rival')
  })

  it('the team list of a competition comes from its report index: ids and names, sorted, once each', async () => {
    expect(await loadReportTeams(FEB)).toEqual([
      { id: '101', name: 'ALPHA' }, { id: '102', name: 'BRAVO' }, { id: '103', name: 'CHARLIE' }, { id: '104', name: 'DELTA' },
    ])
  })

  it('a competition or team that is not published is unavailable (the caller falls back to the API), not an access problem', async () => {
    await expect(loadWebReport('NO_SUCH_COMPETITION', '1', 'own')).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadWebReport(FEB, '999', 'own')).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadReportTeams('NO_SUCH_COMPETITION')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('refuses a manifest of another schema, or a host that is down, as unavailable', async () => {
    override['index.json'] = JSON.stringify({ ...JSON.parse(read('index.json')), schema: 99 })
    await expect(loadWebReport(FEB, '101', 'own')).rejects.toBeInstanceOf(WebDataUnavailable)
    resetWebData()
    override = { 'index.json': null }
    await expect(loadWebReport(FEB, '101', 'own')).rejects.toBeInstanceOf(WebDataUnavailable)
  })
})

describe('access: once the beta is closed the reader needs an invitation', () => {
  it('without the open key and without rights, the report says what is missing (ScopedAccessError)', async () => {
    withoutOpenKey()
    await expect(loadWebReport(FEB, '101', 'own')).rejects.toBeInstanceOf(ScopedAccessError)
  })

  it('the invitation of a club opens its own analysis and the scouting of every rival, but not the analysis of another club', async () => {
    withoutOpenKey()
    addRight(await invitation('club:101'))
    expect((await loadWebReport(FEB, '101', 'own')).team).toBe('ALPHA')
    expect((await loadWebReport(FEB, '102', 'rival')).mode).toBe('rival')
    await expect(loadWebReport(FEB, '102', 'own')).rejects.toBeInstanceOf(ScopedAccessError)       // BRAVO's analysis is for BRAVO's staff
  })

  it('the key of the competition opens everything in it', async () => {
    withoutOpenKey()
    addRight(await invitation(`competicion:${FEB}`))
    expect((await loadWebReport(FEB, '103', 'own')).team).toBe('CHARLIE')
  })

  it('a key of a club of another competition opens nothing here', async () => {
    withoutOpenKey()
    addRight(await invitation('club:34001'))
    await expect(loadWebReport(FEB, '101', 'own')).rejects.toBeInstanceOf(ScopedAccessError)
  })
})

describe('a manifest that was replaced while the page was open', () => {
  it('a file that is gone (404) makes it read the manifest again, once (not in a loop), and carry on', async () => {
    await loadReportTeams(FEB)                                              // the page holds the manifest and the index of the competition
    const manifest = JSON.parse(read('index.json'))
    const entry = manifest.reports.find((r: { collection: string }) => r.collection === FEB)
    const old = JSON.parse(read(entry.file)).reports.find((r: { team_id: string; mode: string }) => r.team_id === '101' && r.mode === 'own')
    override[old.file] = null                                               // the publication moved on: the old file is gone
    requested.length = 0
    await loadWebReport(FEB, '101', 'own').catch(() => undefined)
    expect(requested.filter(f => f === 'index.json').length).toBe(1)        // asked again, once
  })
})

// The full scouting of the rival (issue #638): one sealed file per team and scope — Liga, Copa or both («Agrupado») — read like a report.
describe('the scouting of web-data', () => {
  it('lists the scopes a team has, the league first (a team without cup games has only the league)', async () => {
    expect(await loadScoutingScopes(FEB, '101')).toEqual(['liga', 'copa', 'todo'])
    expect(await loadScoutingScopes(FEB, '999')).toEqual([])
    expect(await loadScoutingScopes(FBCYL, '34001')).toEqual([])                           // FBCYL has no scouting
  })

  it('opens each scope with what it counts: the league, the cup, both', async () => {
    const [liga, copa, todo] = await Promise.all((['liga', 'copa', 'todo'] as const).map(scope => loadWebScouting(FEB, '101', scope)))
    expect([liga.scope, copa.scope, todo.scope]).toEqual(['liga', 'copa', 'todo'])
    expect([liga.sample_games, copa.sample_games, todo.sample_games]).toEqual([2, 1, 3])
    expect(todo.games.map(g => g.competition)).toEqual(['liga', 'copa', 'liga'])
  })

  it('a scope the team does not have is unavailable, not an access problem', async () => {
    await expect(loadWebScouting(FEB, '999', 'liga')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('the staff of any club of the competition opens it, a reader without keys is asked for an invitation', async () => {
    withoutOpenKey()
    await expect(loadWebScouting(FEB, '101', 'liga')).rejects.toBeInstanceOf(ScopedAccessError)
    addRight(await invitation('club:102'))
    expect((await loadWebScouting(FEB, '101', 'liga')).team.id).toBe('101')                 // a rival report: it is for the clubs that will face the team
  })

  it('the own analysis of a club is still its own: the scouting key does not change that', async () => {
    withoutOpenKey()
    addRight(await invitation('club:102'))
    await expect(loadWebReport(FEB, '101', 'own')).rejects.toBeInstanceOf(ScopedAccessError)
  })
})

// Issue #673 (P4): the rows of the contract (what the season tables are computed from on the device) come from the publication too, sealed by competition.
describe('the rows of web-data, opened in the browser', () => {
  it('opens the rows of a FEB competition with the open key of the beta: team rows and player rows, as the exporter wrote them', async () => {
    const rows = await loadWebRows(FEB)
    expect(rows.league).toBe('feb')
    expect(rows.games).toBeGreaterThan(0)
    expect(rows.team_rows.length).toBeGreaterThan(0)
    expect(rows.player_rows?.length).toBeGreaterThan(0)
    expect(requested.filter(f => f.startsWith('rows/'))).toHaveLength(1)
  })

  it('opens the rows of a FBCYL competition too', async () => {
    const rows = await loadWebRows(FBCYL)
    expect(rows.league).toBe('fbcyl')
    expect(rows.team_rows.length).toBeGreaterThan(0)
  })

  it('a competition that is not published is unavailable (the caller falls back), not an access problem', async () => {
    await expect(loadWebRows('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('once the beta is closed, a reader without the key of the competition is asked for an invitation, and the key of the competition opens them', async () => {
    withoutOpenKey()
    await expect(loadWebRows(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    addRight(await invitation(`competicion:${FEB}`))
    expect((await loadWebRows(FEB)).team_rows.length).toBeGreaterThan(0)
  })
})

// Issue #676 (P4, block B): the `DERIVED` of each game of a competition, in a sealed file of its own.
describe('the DERIVED of web-data, opened in the browser', () => {
  it('opens the DERIVED of a FEB competition with the open key of the beta: a row per game with its teams, and the coverage figures', async () => {
    const derived = await loadWebDerived(FEB)
    expect(derived.league).toBe('feb')
    expect(derived.rows.length).toBeGreaterThan(0)
    expect(derived.total).toBe(derived.games + derived.without_derived.length)
    expect(derived.rows[0].teams).toHaveLength(2)
    expect(requested.filter(f => f.startsWith('derived/'))).toHaveLength(1)
    expect(requested.some(f => f.startsWith('rows/'))).toBe(false)                // the team tables do not pay for it, nor it for them
  })

  it('opens the DERIVED of a FBCYL competition too', async () => {
    expect((await loadWebDerived(FBCYL)).league).toBe('fbcyl')
  })

  it('a competition with no DERIVED published is unavailable (the caller falls back), not an access problem', async () => {
    await expect(loadWebDerived('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('once the beta is closed it asks for the key of the competition, like the rows', async () => {
    withoutOpenKey()
    await expect(loadWebDerived(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    addRight(await invitation(`competicion:${FEB}`))
    expect((await loadWebDerived(FEB)).rows.length).toBeGreaterThan(0)
  })
})

// Issues #684 and #685: the shots and the rotations of a competition, each in a sealed file of its own.
describe('the shots and the rotations of web-data, opened in the browser', () => {
  it('opens the shots of a competition: rows of [team, player, x, y, made, zone], and nothing else is downloaded', async () => {
    const shots = await loadWebShots(FEB)
    expect(shots.columns).toEqual(['team_id', 'player_id', 'x', 'y', 'made', 'zone'])
    expect(shots.shots.length).toBeGreaterThan(0)
    expect(requested.filter(f => f.startsWith('shots/'))).toHaveLength(1)
    expect(requested.some(f => f.startsWith('rows/') || f.startsWith('derived/'))).toBe(false)
  })

  it('opens the FBCYL shots too', async () => {
    expect((await loadWebShots(FBCYL)).league).toBe('fbcyl')
  })

  it('opens the rotation analysis of every team of a competition', async () => {
    const rotations = await loadWebRotations(FEB)
    expect(rotations.teams.length).toBeGreaterThan(0)
    expect(rotations.teams[0].analysis.games_with_playbyplay).toBeGreaterThan(0)
  })

  it('opens the lineups of a competition: the per-game counters of every team, in the columns of the contract (issue #686)', async () => {
    const lineups = await loadWebLineups(FEB)
    expect(lineups.columns[0]).toBe('game')
    expect(lineups.teams.length).toBeGreaterThan(0)
    expect(requested.filter(f => f.startsWith('lineups/'))).toHaveLength(1)
  })

  it('opens the IN/OUT of the players of a FEB competition, and FBCYL has none (issue #678)', async () => {
    const inout = await loadWebInOut(FEB)
    expect(inout.players.length).toBeGreaterThan(0)
    expect(requested.filter(f => f.startsWith('inout/'))).toHaveLength(1)
    await expect(loadWebInOut(FBCYL)).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('a competition with neither is unavailable (the caller falls back), not an access problem', async () => {
    await expect(loadWebShots('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadWebRotations('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadWebLineups('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadWebInOut('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('once the beta is closed they ask for the key of the competition, like the rows', async () => {
    withoutOpenKey()
    await expect(loadWebShots(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    await expect(loadWebRotations(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    await expect(loadWebLineups(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    await expect(loadWebInOut(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    addRight(await invitation(`competicion:${FEB}`))
    expect((await loadWebShots(FEB)).shots.length).toBeGreaterThan(0)
    expect((await loadWebRotations(FEB)).teams.length).toBeGreaterThan(0)
    expect((await loadWebLineups(FEB)).teams.length).toBeGreaterThan(0)
  })
})

// Issue #677: the match list and the analysis of every match of a competition, in a sealed file of its own.
describe('the matches of web-data, opened in the browser', () => {
  it('opens the list and the analysis of every match of a FEB competition, in one file', async () => {
    const published = await loadWebMatches(FEB)
    expect(published.league).toBe('feb')
    expect(published.matches).toHaveLength(12)
    expect(published.matches[0].analysis?.comparison.length).toBeGreaterThan(0)
    expect(published.matches[0].home_team).toBeTruthy()
    expect(requested.filter(f => f.startsWith('matches/'))).toHaveLength(1)
  })

  it('opens the FBCYL matches too, and a competition that has none is unavailable, not an access problem', async () => {
    expect((await loadWebMatches(FBCYL)).league).toBe('fbcyl')
    await expect(loadWebMatches('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('once the beta is closed it asks for the key of the competition', async () => {
    withoutOpenKey()
    await expect(loadWebMatches(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    addRight(await invitation(`competicion:${FEB}`))
    expect((await loadWebMatches(FEB)).matches).toHaveLength(12)
  })
})

// Issue #679: the possessions page of a competition (table, consistency, quality CSV) and, apart, its per-possession CSV.
describe('the possessions of web-data, opened in the browser', () => {
  it('opens the table, the consistency and the quality CSV of a competition in one file', async () => {
    const published = await loadWebPossessions(FEB)
    expect(published.table.length).toBeGreaterThan(0)
    expect(published.table[0]).toHaveProperty('team_name')
    expect(Object.keys(published.consistency).sort()).toEqual(['own', 'rival'])
    expect(published.quality_csv).toContain('ID_Partido')
    expect(requested.filter(f => f.startsWith('possessions/'))).toHaveLength(1)
    expect(requested.some(f => f.startsWith('possession_csv/'))).toBe(false)         // the heavy file is only read when the button is pressed
  })

  it('opens the FBCYL ones too', async () => {
    expect((await loadWebPossessions(FBCYL)).table.length).toBeGreaterThan(0)
  })

  it('a competition with no per-possession CSV (no possessions to list) or not published is unavailable, not an access problem', async () => {
    await expect(loadWebPossessionCsv(FEB)).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadWebPossessions('NOPE_2030')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('once the beta is closed it asks for the key of the competition', async () => {
    withoutOpenKey()
    await expect(loadWebPossessions(FEB)).rejects.toBeInstanceOf(ScopedAccessError)
    addRight(await invitation(`competicion:${FEB}`))
    expect((await loadWebPossessions(FEB)).table.length).toBeGreaterThan(0)
  })
})
