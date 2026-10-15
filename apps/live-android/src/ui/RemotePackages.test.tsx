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

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const fixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo.bpkg'), 'utf8')
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const PASS = 'clave-de-prueba-1'
const PASS_KEY = 'basketlab-live-passphrase'

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

async function fetcher(over: { sha?: string } = {}) {
  const index = {
    v: 1, generated_at: '2026-10-09T11:42:25+00:00',
    packages: [{
      team_id: '1008631', rival_id: '1008898', rival: 'RECOLETAS ZAMORA', file: '1008631/1008898.bpkg',
      sha256: over.sha ?? (await sha(fixture)), bytes: 100,
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
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
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

  it('a failed download says nothing is available and keeps the button', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: 'otra-clave-distinta' } })
    download()
    await screen.findByRole('alert')
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('button', { name: /ya disponible/i })).toBeNull()
  })
})

describe('RemotePackages', () => {
  it('lists the published packages with rival and date', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    expect(await screen.findByText(/RECOLETAS ZAMORA/)).toBeTruthy()
    expect(screen.getByText(/10\/10\/2026/)).toBeTruthy()
  })

  it('marks the list and the password field with the classes the styles use (issue #210)', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(container.querySelector('ul.remote-packages > li > span')).toBeTruthy()
    expect(container.querySelector('ul.remote-packages > li > button')).toBeTruthy()
    expect(container.querySelector('label.remote-packages-pass input[type="password"]')).toBeTruthy()
  })

  it('a wrong password says how many characters were typed, so a missing letter or a stray space shows (issue #337)', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: 'otra-clave-distinta' } })
    download()
    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/contraseña/i)
    expect(alert.textContent).toMatch(/escribiste 19 caracteres/i)
    expect(store.saved).toBeNull()
  })

  it('has a button to see the password and tolerates the spaces of a keyboard', async () => {
    const store = memoryStore()
    const onLoaded = vi.fn()
    render(<RemotePackages engine={engine()} store={store} onLoaded={onLoaded} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    expect(screen.getByRole('button', { name: /mostrar contraseña/i })).toBeTruthy()
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: ` ${PASS} ` } })
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
  })

  it('downloads, decrypts, installs and remembers the password', async () => {
    const store = memoryStore()
    const eng = engine()
    const onLoaded = vi.fn()
    const f = await fetcher()
    render(<RemotePackages engine={eng} store={store} onLoaded={onLoaded} fetcher={f} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
    expect(f).toHaveBeenCalledWith(`${PACKAGES_BASE_URL}/1008631/1008898.bpkg`, expect.anything())
    expect(eng.start).toHaveBeenCalledWith(demoPackage)
    expect(store.saved?.plaintext).toBe(demoPackage)
    expect(localStorage.getItem(PASS_KEY)).toBe(PASS)
  })

  it('uses the remembered password without asking again', async () => {
    localStorage.setItem(PASS_KEY, PASS)
    const onLoaded = vi.fn()
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={onLoaded} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    download()
    await waitFor(() => expect(onLoaded).toHaveBeenCalled())
  })

  it('a wrong password shows an error and neither installs nor remembers it', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: 'incorrecta-123' } })
    download()
    expect(await screen.findByText(/contraseña/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
    expect(localStorage.getItem(PASS_KEY)).toBeNull()
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
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
    download()
    expect(await screen.findByText(/no coincide/i, { selector: '[role="alert"]' })).toBeTruthy()
    expect(store.saved).toBeNull()
  })

  it('says when no packages are published', async () => {
    const f = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) })
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={f} />)
    expect(await screen.findByText(/no hay paquetes publicados/i)).toBeTruthy()
  })
})

describe('RemotePackages help (issue #225)', () => {
  it('explains where the password of the published packages comes from', async () => {
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await fetcher()} />)
    await screen.findByText(/RECOLETAS ZAMORA/)
    fireEvent.click(screen.getByRole('button', { name: /ayuda sobre los paquetes publicados/i }))
    const text = screen.getByRole('note').textContent ?? ''
    expect(text).toMatch(/van cifrados/i)
    expect(text).toMatch(/PACKAGE_PASSWORD/)
    expect(text).toMatch(/queda guardada en este dispositivo/i)
  })
})

// --- the whole round of every competition (issues #286, #172) ---------------------------------------------------------------------

const roundFixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_round.bpkgz'), 'utf8')

async function roundFetcher(over: { club?: boolean } = {}) {
  const side = (id: string, name: string) => ({ id, name })
  const matches = [
    { code: '101', start: '2026-10-17T12:00', home: side('11', 'EQ 11'), away: side('12', 'EQ 12'), own_id: '11', own_ids: ['11', '12'], is_club: false },
    { code: '102', start: '2026-10-17T17:00', home: side('1008631', 'LEON'), away: side('1008898', 'ZAMORA'), own_id: '1008631', own_ids: ['1008631', '1008898'], is_club: true },
    { code: '103', start: '2026-10-17T19:00', home: side('31', 'EQ 31'), away: side('32', 'EQ 32'), own_id: '31', own_ids: ['31', '32'], is_club: false },
  ]
  const index = {
    v: 1, packages: [], club_team_id: '1008631', rounds: [
      { collection: 'OTRA_COMPETICION_2026', round: 2, file: 'rounds/OTRA__r2.bpkgz', sha256: 'x', bytes: 1000, club: false,
        matches: [{ code: '900', start: '2026-10-17T10:00', home: side('91', 'LOCAL 91'), away: side('92', 'VISIT 92'), own_id: '91', is_club: false }] },
      { collection: 'DEMO_2026', round: 4, file: 'rounds/DEMO__r4.bpkgz', sha256: await sha(roundFixture), bytes: 70000, club: over.club ?? true, matches },
    ],
  }
  return vi.fn(async (url: string) => {
    const body = url.endsWith('index.json') ? JSON.stringify(index) : roundFixture
    return { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  })
}

describe('RemotePackages: the round of every competition', () => {
  it('lists the competitions with the club first, and in the round the club match first', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} />)
    await screen.findByText(/DEMO 2026/)
    const headings = Array.from(container.querySelectorAll('.round-packages h3')).map(h => h.textContent)
    expect(headings[0]).toMatch(/DEMO 2026.*jornada 4/)
    expect(headings[1]).toMatch(/OTRA COMPETICION 2026.*jornada 2/)
    const rows = Array.from(container.querySelectorAll('.round-packages')[0].querySelectorAll('li')).map(li => li.textContent)
    expect(rows[0]).toMatch(/LEON.*ZAMORA/)
    expect(rows[1]).toMatch(/EQ 11/)
    expect(rows[2]).toMatch(/EQ 31/)
  })

  it('every match offers to follow it as either of its two teams, the default one first (issue #286)', async () => {
    const { container } = render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} />)
    await screen.findByText(/DEMO 2026/)
    const clubRow = container.querySelectorAll('.round-packages')[0].querySelectorAll('li')[0] as HTMLElement
    expect(Array.from(clubRow.querySelectorAll('button')).map(b => b.textContent)).toEqual(['Seguir como LEON', 'Seguir como ZAMORA'])
    expect(screen.getByRole('button', { name: /descargar LEON contra ZAMORA como ZAMORA/i })).toBeTruthy()
    // an index from before both sides existed: one button per match, as before
    expect(container.querySelectorAll('.round-packages')[1].querySelectorAll('li button')).toHaveLength(1)
  })

  it('downloads the bundle once, decrypts it once and installs the package of the chosen match', async () => {
    const store = memoryStore()
    const eng = engine()
    const onLoaded = vi.fn()
    const f = await roundFetcher()
    render(<RemotePackages engine={eng} store={store} onLoaded={onLoaded} fetcher={f} />)
    await screen.findByText(/DEMO 2026/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
    fireEvent.click(screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 31/i }))
    await waitFor(() => expect(onLoaded).toHaveBeenCalledTimes(1))
    expect(eng.start).toHaveBeenCalledWith(demoPackage)
    expect(store.saved?.plaintext).toBe(demoPackage)
    fireEvent.click(screen.getByRole('button', { name: /descargar EQ 11 contra EQ 12 como EQ 12/i }))
    await waitFor(() => expect(onLoaded).toHaveBeenCalledTimes(2))
    expect(f.mock.calls.filter(c => String(c[0]).endsWith('.bpkgz'))).toHaveLength(1)     // the bundle is not downloaded twice
    expect(localStorage.getItem(PASS_KEY)).toBe(PASS)
  })

  it('a wrong password says so and installs nothing', async () => {
    const store = memoryStore()
    render(<RemotePackages engine={engine()} store={store} onLoaded={vi.fn()} fetcher={await roundFetcher()} />)
    await screen.findByText(/DEMO 2026/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: 'otra-clave-distinta' } })
    fireEvent.click(screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 31/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/contraseña/i)
    expect(store.saved).toBeNull()
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
    await screen.findByText(/DEMO 2026/)
    fireEvent.change(screen.getByLabelText(/contraseña/i), { target: { value: PASS } })
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
    localStorage.setItem(PASS_KEY, PASS)
    render(<RemotePackages engine={engine()} store={memoryStore()} onLoaded={vi.fn()} fetcher={await roundFetcher()} loaded={loadedSummary('103', '32')} />)
    await screen.findByText(/DEMO 2026/)
    expect((screen.getByRole('button', { name: /EQ 31 contra EQ 32 como EQ 32/i }) as HTMLButtonElement).textContent).toMatch(/ya disponible/i)
    expect((screen.getByRole('button', { name: /descargar EQ 31 contra EQ 32 como EQ 31/i }) as HTMLButtonElement).disabled).toBe(false)
  })
})
