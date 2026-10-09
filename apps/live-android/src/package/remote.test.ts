import { webcrypto } from 'node:crypto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PACKAGES_BASE_URL, fetchIndex, fetchPackageText, type PackageIndexEntry } from './remote'

const TEXT = '{"v":1,"alg":"AES-256-GCM"}'
async function sha(text: string) {
  const buf = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('')
}
const entry = (over: Partial<PackageIndexEntry> = {}): PackageIndexEntry => ({
  team_id: '1008631', rival_id: '1008898', rival: 'RECOLETAS ZAMORA', file: '1008631/1008898.bpkg', sha256: 'x', bytes: 10,
  match: { code: '2524470', start: '2026-10-10T17:00', round: 2, home: { id: '1', name: 'A' }, away: { id: '2', name: 'B' } }, ...over,
})
const reply = (body: string, ok = true, status = 200) =>
  vi.fn().mockResolvedValue({ ok, status, text: async () => body, json: async () => JSON.parse(body) })

beforeEach(() => vi.stubGlobal('crypto', webcrypto))

describe('fetchIndex', () => {
  it('reads index.json from the live-packages branch', async () => {
    const f = reply(JSON.stringify({ v: 1, generated_at: 't', packages: [entry()] }))
    const index = await fetchIndex(f)
    expect(f).toHaveBeenCalledWith(`${PACKAGES_BASE_URL}/index.json`, expect.anything())
    expect(index.packages[0].rival).toBe('RECOLETAS ZAMORA')
  })

  it('rejects an unknown index version', async () => {
    await expect(fetchIndex(reply(JSON.stringify({ v: 9, packages: [] })))).rejects.toThrow(/versión/i)
  })

  it('reports an HTTP error (branch not published yet)', async () => {
    await expect(fetchIndex(reply('Not Found', false, 404))).rejects.toThrow(/404/)
  })

  it('reports being offline', async () => {
    await expect(fetchIndex(vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))).rejects.toThrow(/conexión/i)
  })
})

describe('fetchPackageText', () => {
  it('downloads the package and checks its SHA-256', async () => {
    const f = reply(TEXT)
    expect(await fetchPackageText(entry({ sha256: await sha(TEXT) }), f)).toBe(TEXT)
    expect(f.mock.calls[0][0]).toBe(`${PACKAGES_BASE_URL}/1008631/1008898.bpkg`)
  })

  it('refuses a package whose checksum differs from the index (stale CDN cache or corruption)', async () => {
    await expect(fetchPackageText(entry({ sha256: 'deadbeef' }), reply(TEXT))).rejects.toThrow(/no coincide/i)
  })
})
