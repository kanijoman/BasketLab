import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { ScopedAccessError } from '@live-package/crypto'
import { addRight, parseInvite, type Right } from '@live-package/rights'
import { loadReportTeams, loadWebReport, resetWebData, setDataBase, WebDataUnavailable } from './client'

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
