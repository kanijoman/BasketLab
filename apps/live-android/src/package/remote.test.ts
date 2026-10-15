import { webcrypto } from 'node:crypto'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PACKAGES_BASE_URL, fetchIndex, fetchPackageText, fetchRoundText, orderRounds, parseRoundBundle, pickPackage, sidesOf, type PackageIndexEntry, type RoundIndexEntry } from './remote'

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
    await expect(fetchIndex(reply('Not Found', false, 404))).rejects.toThrow(/actualizar la lista/i)  // what to do (#225)
  })

  it('reports being offline', async () => {
    await expect(fetchIndex(vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))).rejects.toThrow(/conexión/i)
    await expect(fetchIndex(vi.fn().mockRejectedValue(new TypeError('x')))).rejects.toThrow(/revisa la conexión/i)  // what to do (#225)
  })
})

const round = (over: Partial<RoundIndexEntry> = {}): RoundIndexEntry => ({
  collection: 'LF_CHALLENGE_2026', round: 3, file: 'rounds/LF_CHALLENGE_2026__r3.bpkgz', sha256: 'x', bytes: 70_000, club: false,
  matches: [], ...over,
})
const roundMatch = (code: string, start: string, isClub = false) => ({
  code, start, home: { id: `h${code}`, name: `H${code}` }, away: { id: `a${code}`, name: `A${code}` }, own_id: `h${code}`, is_club: isClub,
})

describe('rounds of the index (issues #286, #172)', () => {
  it('keeps the rounds and the club of the index; an index without them is just the club packages', async () => {
    const withRounds = await fetchIndex(reply(JSON.stringify({ v: 1, packages: [], rounds: [round()], club_team_id: '1008631' })))
    expect(withRounds.rounds).toHaveLength(1)
    expect(withRounds.club_team_id).toBe('1008631')
    const old = await fetchIndex(reply(JSON.stringify({ v: 1, packages: [entry()] })))
    expect(old.rounds).toEqual([])
  })

  it('downloads a bundle and checks its SHA-256 like a package', async () => {
    const f = reply(TEXT)
    expect(await fetchRoundText(round({ sha256: await sha(TEXT) }), f)).toBe(TEXT)
    expect(f.mock.calls[0][0]).toBe(`${PACKAGES_BASE_URL}/rounds/LF_CHALLENGE_2026__r3.bpkgz`)
    await expect(fetchRoundText(round({ sha256: 'deadbeef' }), reply(TEXT))).rejects.toThrow(/no coincide/i)
  })

  it('puts the competition of the club first, and in each round the matches of the club first, then by time', () => {
    const ordered = orderRounds([
      round({ collection: 'A', matches: [roundMatch('1', '2026-10-17T19:00')] }),
      round({ collection: 'B', club: true, matches: [roundMatch('2', '2026-10-17T12:00'), roundMatch('3', '2026-10-17T17:00', true), roundMatch('4', '2026-10-17T10:00')] }),
    ])
    expect(ordered.map(r => r.collection)).toEqual(['B', 'A'])
    expect(ordered[0].matches.map(m => m.code)).toEqual(['3', '4', '2'])
  })

  it('the sides that can be followed in a match: both teams, or just the default one in an older index (issue #286)', () => {
    expect(sidesOf({ ...roundMatch('1', 's'), own_ids: ['h1', 'a1'] })).toEqual(['h1', 'a1'])
    expect(sidesOf(roundMatch('1', 's'))).toEqual(['h1'])
  })

  it('picks the package of the chosen side, and the first one of the match when the bundle has only that', () => {
    const entry = (ownId: string, text: string) => ({ match: roundMatch('1', 's'), own_id: ownId, rival_id: 'x', is_club: false, package: text })
    const both = { v: 1, collection: 'A', round: 3, matches: [entry('h1', 'HOME'), entry('a1', 'AWAY'), { ...entry('h2', 'OTRO'), match: roundMatch('2', 's') }] }
    expect(pickPackage(both, '1', 'a1')).toBe('AWAY')
    expect(pickPackage(both, '1', 'h1')).toBe('HOME')
    const older = { ...both, matches: [entry('h1', 'HOME')] }
    expect(pickPackage(older, '1', 'a1')).toBe('HOME')       // a bundle published before both sides existed: the only one
    expect(pickPackage(both, '9', 'h1')).toBeNull()
  })

  it('parses a bundle and refuses one of another version or shape', () => {
    const ok = { v: 1, collection: 'A', round: 3, matches: [{ match: roundMatch('1', 's'), own_id: 'h1', rival_id: 'a1', is_club: false, package: '{}' }] }
    expect(parseRoundBundle(JSON.stringify(ok)).matches[0].package).toBe('{}')
    expect(() => parseRoundBundle(JSON.stringify({ ...ok, v: 9 }))).toThrow(/versión/i)
    expect(() => parseRoundBundle('no json')).toThrow(/jornada/i)
    expect(() => parseRoundBundle(JSON.stringify({ v: 1 }))).toThrow(/jornada/i)
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
