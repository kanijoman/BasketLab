import { webcrypto } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RemotePackages from './RemotePackages'
import type { PackageSummary } from '../package/summary'
import type { PackageStore, StoredPackage } from '../package/storage'
import type { EngineApi } from '../engine/client'
import { PACKAGES_BASE_URL } from '../package/remote'

// The packages open with the key of the scope the index publishes: nobody types a password (the password of the packages was removed).
const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const demo = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_scoped.json'), 'utf8'))
const fixture: string = demo.package.file
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const OLD_PASS_KEY = 'basketlab-live-passphrase'

async function sha(text: string) {
  const buf = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('')
}

function memoryStore(): PackageStore & { saved: StoredPackage | null } {
  const s = {
    saved: null as StoredPackage | null,
    load: async () => s.saved,
    save: async (r: StoredPackage) => { s.saved = r },
    clear: async () => { s.saved = null },
  }
  return s
}
const META = { team: { id: '1', name: 'A' }, rival: { id: '2', name: 'B' } }
const engine = () => ({ start: vi.fn().mockResolvedValue(META) }) as unknown as EngineApi & { start: ReturnType<typeof vi.fn> }

async function fetcher(over: { sha?: string; legacy?: boolean } = {}) {
  const index = {
    v: over.legacy ? 1 : 2, generated_at: '2026-10-09T11:42:25+00:00', ...(over.legacy ? {} : { open_key: demo.open_key }),
    packages: [{
      team_id: '1008631', rival_id: '1008898', rival: 'RECOLETAS ZAMORA', file: '1008631/1008898.bpkg',
      sha256: over.sha ?? (await sha(fixture)), bytes: 100, ...(over.legacy ? {} : { wraps: demo.package.wraps }),
      match: { code: '2524470', start: '2026-10-10T17:00', round: 2, home: { id: '1008898', name: 'RECOLETAS ZAMORA' }, away: { id: '1008631', name: 'LEON' } },
    }],
  }
  return vi.fn(async (url: string) => {
    const body = url.endsWith('index.json') ? JSON.stringify(index) : fixture
    return { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  })
}

const download = () => fireEvent.click(screen.getByRole('button', { name: /descargar/i }))

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
  localStorage.clear()
})

const loadedSummary = (code: string, teamId: string): PackageSummary => ({
  team: 'EQ', teamId, rival: 'RV', rivalId: 'x', season: '2026', collection: 'C', createdAt: '', ownPlayers: 1, rivalPlayers: 1,
  games: { own: 1, rival: 1, league: 1 }, match: { code },
})

// Issue #342: after a download nothing said it had worked, and the button stayed as if nothing had happened
describe('RemotePackages: feedback of the download (issue #342)', () => {
  it('says the match is loaded and turns its button into «Ya disponible», disabled', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    download()
    const done = await screen.findByRole('status')
    expect(done.textContent).toMatch(/descargado/i)
    expect(done.textContent).toMatch(/pestaña Partido/i)
    const button = screen.getByRole('button', { name: /ya disponible/i }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
    expect(screen.queryByRole('button', { name: /^descargar$/i })).toBeNull()
  })

  it('a package that was already loaded (the app was reopened) shows as available from the start', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} loaded={loadedSummary('2524470', '1008631')} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect((screen.getByRole('button', { name: /ya disponible/i }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('another loaded match leaves this one downloadable', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} loaded={loadedSummary('999', '1008631')} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(screen.queryByRole('button', { name: /ya disponible/i })).toBeNull()
  })
})

describe('RemotePackages', () => {
  it('lists the published packages with rival and date', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    expect(await screen.findByText(/RECOLETAS ZAMORA/)).toBeTruthy()
    expect(screen.getByText(/10\/10\/2026/)).toBeTruthy()
  })

  it('marks the list with the classes the styles use (issue #210)', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(container.querySelector('ul.remote-packages > li > span')).toBeTruthy()
    expect(container.querySelector('ul.remote-packages > li > button')).toBeTruthy()
  })

  it('downloads, decrypts and installs with no password anywhere on the screen', async () => {
    const store = memoryStore()
    const eng = engine()
    const onLoaded = vi.fn()
    const f = await fetcher()
    const { container } = render(<RemotePackages engine={eng} store={store} onLoaded={onLoaded} fetcher={f} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(screen.queryByLabelText(/contraseña/i)).toBeNull()
    expect(container.querySelector('input[type="password"]')).toBeNull()
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    expect(f).toHaveBeenCalledWith(`${PACKAGES_BASE_URL}/1008631/1008898.bpkg`, expect.anything())
    expect(eng.start).toHaveBeenCalledWith(demoPackage)
    expect(store.saved?.plaintext).toBe(demoPackage)
    expect(localStorage.getItem(OLD_PASS_KEY)).toBeNull()
  })

  it('a package of an old publication (sealed with a password) is not offered: the screen says to wait for the new one, with no password field', async () => {
    const store = memoryStore()
    const { container } = render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await fetcher({ legacy: true })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect((screen.getByRole('button', { name: /^descargar$/i }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/formato antiguo/i)).toBeTruthy()
    expect(screen.queryByLabelText(/contraseña/i)).toBeNull()
    expect(container.querySelector('input[type="password"]')).toBeNull()
    expect(store.saved).toBeNull()
  })

  it('offline: says so and keeps the installed package untouched', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()}
      fetcher={vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))} />)
    expect(await screen.findByText(/conexión/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('a checksum mismatch is reported and nothing is installed', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await fetcher({ sha: 'deadbeef' })} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    download()
    expect(await screen.findByText(/no coincide/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('says when no packages are published', async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) })
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={f} />)
    expect(await screen.findByText(/no hay partidos publicados/i)).toBeTruthy()
  })
})

// --- the whole round of every competition (issues #286, #172) ---------------------------------------------------------------------

const b64 = (bytes: ArrayBuffer | Uint8Array) => Buffer.from(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes)).toString('base64')

/** Seals a text by scope as the publisher does (src/live_prep/package_scopes.py): a random key for the file, wrapped with the key of the open scope. */
async function sealOpen(plaintext: string) {
  const subtle = webcrypto.subtle
  const cek = webcrypto.getRandomValues(new Uint8Array(32))
  const iv = webcrypto.getRandomValues(new Uint8Array(12))
  const wrapIv = webcrypto.getRandomValues(new Uint8Array(12))
  const body = await subtle.encrypt({ name: 'AES-GCM', iv }, await subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']), new TextEncoder().encode(plaintext))
  const openKey = await subtle.importKey('raw', Buffer.from(demo.open_key, 'base64'), 'AES-GCM', false, ['encrypt'])
  const wrapped = await subtle.encrypt({ name: 'AES-GCM', iv: wrapIv, additionalData: new TextEncoder().encode('abierto') }, openKey, cek)
  return { file: JSON.stringify({ v: 2, alg: 'AES-256-GCM', iv: b64(iv), ciphertext: b64(body) }), wraps: [{ scope: 'abierto', iv: b64(wrapIv), key: b64(wrapped) }] }
}

/** The bundle of a round: every match once per team, each with the demo package. */
async function sealedRound() {
  const rows = (code: string, a: string, b: string) => [a, b].map(own => ({ match: { code }, own_id: own, rival_id: own === a ? b : a, is_club: false, package: demoPackage }))
  const plain = JSON.stringify({ v: 1, collection: 'DEMO_2026', round: 4, matches: [...rows('101', '11', '12'), ...rows('102', '1008631', '1008898'), ...rows('103', '31', '32')] })
  const sealed = await sealOpen(plain)
  return { ...sealed, sha: await sha(sealed.file) }
}

async function roundFetcher(over: { club?: boolean; withPackage?: boolean } = {}) {
  const round = await sealedRound()
  const side = (id: string, name: string) => ({ id, name })
  const matches = [
    { code: '101', start: '2027-10-17T12:00', home: side('11', 'EQ 11'), away: side('12', 'EQ 12'), own_id: '11', own_ids: ['11', '12'], is_club: false },
    { code: '102', start: '2027-10-17T17:00', home: side('1008631', 'LEON'), away: side('1008898', 'ZAMORA'), own_id: '1008631', own_ids: ['1008631', '1008898'], is_club: true },
    { code: '103', start: '2027-10-17T19:00', home: side('31', 'EQ 31'), away: side('32', 'EQ 32'), own_id: '31', own_ids: ['31', '32'], is_club: false },
  ]
  const index = {
    v: 2, open_key: demo.open_key, club_team_id: '1008631', packages: over.withPackage ? [{
      team_id: '1008631', rival_id: '1008898', rival: 'RECOLETAS ZAMORA', file: '1008631/1008898.bpkg', sha256: 'x', bytes: 100, wraps: demo.package.wraps,
      match: { code: '102', start: '2027-10-17T17:00', round: 2, home: side('1008631', 'LEON'), away: side('1008898', 'RECOLETAS ZAMORA') },
    }] : [], rounds: [
      { collection: 'OTRA_COMPETICION_2026', round: 2, file: 'rounds/OTRA__r2.bpkgz', sha256: 'x', bytes: 1000, club: false, wraps: round.wraps,
        matches: [{ code: '900', start: '2027-10-17T10:00', home: side('91', 'LOCAL 91'), away: side('92', 'VISIT 92'), own_id: '91', is_club: false }] },
      { collection: 'DEMO_2026', round: 4, file: 'rounds/DEMO__r4.bpkgz', sha256: round.sha, bytes: 70000, club: over.club ?? true, wraps: round.wraps, matches },
    ],
  }
  return vi.fn(async (url: string) => {
    const body = url.endsWith('index.json') ? JSON.stringify(index) : round.file
    return { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  })
}

describe('RemotePackages: the round of every competition', () => {
  it('lists the next match of each team by date, with the label of its competition (the club match in bold)', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} />)
    await screen.findAllByText(/EQ 31/)
    const rows = Array.from(container.querySelectorAll('li.round-match'))
    expect(rows.map(li => li.getAttribute('data-code'))).toEqual(['900', '101', '102', '103'])
    expect(rows[2].textContent).toMatch(/DEMO 2026/)
    expect(rows[0].textContent).toMatch(/OTRA COMPETICION 2026/)
    expect(rows[2].querySelector('strong.team-name')?.textContent).toBe('LEON')
  })

  it('every match offers to follow it as either of its two teams, the default one first (issue #286)', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} />)
    await screen.findAllByText(/EQ 31/)
    const clubRow = container.querySelector('li.round-match[data-code="102"]') as HTMLElement
    expect(Array.from(clubRow.querySelectorAll('.round-sides button')).map(b => b.textContent)).toEqual(['Seguir como LEON', 'Seguir como ZAMORA'])
    expect(screen.getByRole('button', { name: /descargar LEON contra ZAMORA como ZAMORA/i })).toBeTruthy()
    // an index from before both sides existed: one button per match, as before
    expect(container.querySelectorAll('li.round-match[data-code="900"] .round-sides button')).toHaveLength(1)
  })

  it('downloads the bundle once, decrypts it once and installs the package of the chosen match, with no password', async () => {
    const store = memoryStore()
    const eng = engine()
    const onLoaded = vi.fn()
    const f = await roundFetcher()
    render(<RemotePackages engine={eng} store={store} onLoaded={onLoaded} fetcher={f} />)
    await screen.findAllByText(/EQ 31/)
    expect(screen.queryByLabelText(/contraseña/i)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 31/i }))
    await waitFor(() => expect(onLoaded).toHaveBeenCalledTimes(1))
    expect(eng.start).toHaveBeenCalledWith(demoPackage)
    expect(store.saved?.plaintext).toBe(demoPackage)
    fireEvent.click(screen.getByRole('button', { name: /descargar EQ 11 contra EQ 12 como EQ 12/i }))
    await waitFor(() => expect(onLoaded).toHaveBeenCalledTimes(2))
    expect(f.mock.calls.filter(c => String(c[0]).endsWith('.bpkgz'))).toHaveLength(1)     // the bundle is not downloaded twice
    expect(localStorage.getItem(OLD_PASS_KEY)).toBeNull()
  })

  it('an index without rounds shows only the club packages, as before', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(screen.queryByText(/jornada completa/i)).toBeNull()
  })
})

describe('RemotePackages: feedback of a round download (issue #342)', () => {
  it('only the side that was downloaded is «Ya disponible»; the other side of the match can still be followed', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} />)
    await screen.findAllByText(/EQ 31/)
    fireEvent.click(screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 31/i }))
    expect((await screen.findByRole('status')).textContent).toMatch(/descargado/i)
    const done = screen.getByRole('button', { name: /EQ 31 contra EQ 32 como EQ 31/i }) as HTMLButtonElement
    expect(done.disabled).toBe(true)
    expect(done.textContent).toMatch(/ya disponible/i)
    const other = screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 32/i }) as HTMLButtonElement
    expect(other.disabled).toBe(false)
    expect(other.textContent).toMatch(/seguir como EQ 32/i)
  })

  it('a loaded package of a round match shows its side as available from the start', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} loaded={loadedSummary('103', '32')} />)
    await screen.findAllByText(/EQ 31/)
    expect((screen.getByRole('button', { name: /EQ 31 contra EQ 32 como EQ 32/i }) as HTMLButtonElement).textContent).toMatch(/ya disponible/i)
    expect((screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 31/i }) as HTMLButtonElement).disabled).toBe(false)
  })
})


// Feedback of 0.4.0 (#569): «Próximos partidos» and «Partidos a seguir» were two lists, one of them with only the rival
describe('RemotePackages: one list of upcoming matches', () => {
  it('has a single title and a single list when the index has packages and rounds: the rounds cover the same matches', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher({ withPackage: true })} />)
    await screen.findAllByText(/EQ 31/)
    expect(screen.getAllByRole('heading', { level: 2 }).map(h => h.textContent)).toEqual(['Próximos partidos'])
    expect(container.querySelectorAll('ul.remote-packages')).toHaveLength(1)
    expect(container.querySelectorAll('li.round-match[data-code="102"]')).toHaveLength(1)
  })

  it('an index without rounds still lists its packages, now with the two teams and not only the rival', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    const row = container.querySelector('ul.remote-packages li') as HTMLElement
    expect(row.textContent).toContain('RECOLETAS ZAMORA')
    expect(row.textContent).toContain('LEON')
    expect(row.querySelector('strong')?.textContent).toBe('LEON')       // ours, in bold
  })
})
