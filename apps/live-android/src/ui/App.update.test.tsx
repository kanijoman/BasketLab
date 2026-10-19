// Version and update in the app (issues #226 and #227): a notice when a newer APK is published, the About panel,
// and nothing that disturbs a match.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { AppUpdateDeps } from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import type { PackageStore, StoredPackage } from '../package/storage'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}
const LATEST = {
  version: '0.3.0', versionCode: 52, apk: 'https://example.test/basketlab-live.apk', notes: 'Alineación indebida',
  built_at: '2026-10-16T07:30:00Z',
}
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })

const engine = (): EngineApi => ({
  start: vi.fn().mockResolvedValue(META),
  loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
  replay: vi.fn(), update: vi.fn(async (): Promise<EngineOutput> => ({
    snapshot: { period: 1, remaining: 593, elapsed: 7, score: { '1': 2, '2': 0 } } as never, alerts: [], analysis: {},
  })),
  loadRecording: vi.fn(), playRecording: vi.fn(), report: vi.fn(), setMode: vi.fn(), dispose: vi.fn(),
})

function memory() {
  const data = new Map<string, string>()
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => { data.set(k, v) }, removeItem: (k: string) => { data.delete(k) } }
}

function deps(over: Partial<AppUpdateDeps> = {}): AppUpdateDeps {
  return {
    getInstalled: async () => ({ name: '0.2.0', build: 40, builtAt: '2026-10-13T08:20:00Z', native: true }),
    fetchJson: vi.fn().mockResolvedValue(LATEST), openUrl: vi.fn(), storage: memory(), ...over,
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})

/** The About panel is in its own tab (issue #224). */
const openAbout = () => fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))

const mount = (d: AppUpdateDeps, extra: object = {}) =>
  render(<App engine={engine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} appUpdate={d} {...extra} />)

/** A device whose "back to the foreground" the test triggers by hand (issue #335). */
function withResume(over: Partial<AppUpdateDeps> = {}) {
  let resume: (() => void) | null = null
  const d = deps({ onResume: cb => { resume = cb; return () => { resume = null } }, ...over })
  return { d, fire: () => resume?.(), listening: () => resume !== null }
}

describe('new versions are noticed without opening Acerca de (issue #335)', () => {
  it('checks again when the app comes back to the foreground, and shows the notice', async () => {
    let now = 1_000_000
    const first = { ...LATEST, version: '0.2.0', versionCode: 40 }       // what was published when the app opened: nothing newer
    const fetchJson = vi.fn().mockResolvedValueOnce(first).mockResolvedValue(LATEST)
    const { d, fire } = withResume({ fetchJson, now: () => now })
    mount(d)
    await screen.findByText('EQUIPO PROPIO')
    await waitFor(() => expect(fetchJson).toHaveBeenCalledTimes(1))
    expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull()
    now += 11 * 60 * 1000                                                 // a release was published and the cache is old
    fire()
    expect((await screen.findByRole('status', { name: /actualización/i })).textContent).toMatch(/versión nueva: 0\.3\.0/i)
    expect(fetchJson).toHaveBeenCalledTimes(2)
  })

  it('does not ask again when it returns within the minutes of the cache', async () => {
    const { d, fire } = withResume({ now: () => 1_000_000 })
    mount(d)
    await screen.findByRole('status', { name: /actualización/i })
    fire()
    await new Promise(resolve => setTimeout(resolve, 20))
    expect(d.fetchJson).toHaveBeenCalledTimes(1)
  })

  it('stops listening when the app closes, and in a browser it never listens for nothing', async () => {
    const { d, listening } = withResume()
    const { unmount } = mount(d)
    await screen.findByRole('status', { name: /actualización/i })
    expect(listening()).toBe(true)
    unmount()
    expect(listening()).toBe(false)
  })
})

describe('update notice', () => {
  it('shows a discreet notice when a newer version is published and opens the APK from its button', async () => {
    const d = deps()
    mount(d)
    await screen.findByText('EQUIPO PROPIO')
    const notice = await screen.findByRole('status', { name: /actualización/i })
    expect(notice.textContent).toMatch(/versión nueva: 0\.3\.0/i)
    fireEvent.click(screen.getByRole('button', { name: /^actualizar$/i }))
    expect(d.openUrl).toHaveBeenCalledWith(LATEST.apk)
  })

  it('says nothing when the installed version is the latest', async () => {
    mount(deps({ getInstalled: async () => ({ name: '0.3.0', build: 52, builtAt: null, native: true }) }))
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    await waitFor(() => expect(screen.getByText(/tienes la última versión/i)).toBeTruthy())
    expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull()
  })

  it('offline it does not complain: no notice and no error screen', async () => {
    mount(deps({ fetchJson: vi.fn().mockRejectedValue(new Error('offline')) }))
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    await waitFor(() => expect(screen.getByRole('button', { name: /buscar actualización/i })).toBeTruthy())
    expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull()
  })

  it('in a browser there is nothing to update and no request is made', async () => {
    const d = deps({ getInstalled: async () => ({ name: 'dev', build: null, builtAt: null, native: false }) })
    mount(d)
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    await waitFor(() => expect(screen.getByText(/versión de desarrollo/i)).toBeTruthy())
    expect(d.fetchJson).not.toHaveBeenCalled()
  })

  it('the About panel shows the version and the button checks again on demand', async () => {
    const d = deps({ getInstalled: async () => ({ name: '0.3.0', build: 52, builtAt: null, native: true }) })
    mount(d)
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    await screen.findByText(/BasketLab Live 0\.3\.0/)
    expect(d.fetchJson).toHaveBeenCalledTimes(1)                      // on opening
    fireEvent.click(screen.getByRole('button', { name: /buscar actualización/i }))
    await waitFor(() => expect(d.fetchJson).toHaveBeenCalledTimes(2)) // the button ignores the cache
  })
})

// --- never during a match ------------------------------------------------------------------

const PKG = JSON.stringify({
  checksum: 'x',
  package: {
    team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, season: '2025-2026',
    collection: 'c', created_at: '2026-10-08T12:00:00Z', tables: { players: {}, rival_players: {} },
    baselines: { sample_games: { own: 5, rival: 4, league: 50 } }, competition_meta: { match: { code: '2524475' } },
  },
})
const SAVED: StoredPackage = { plaintext: PKG, savedAt: '2026-10-09T10:00:00Z' }
const store = (): PackageStore => {
  let saved: StoredPackage | null = SAVED
  return { load: async () => saved, save: async r => { saved = r }, clear: async () => { saved = null } }
}
const pack: Pack = {
  v: 1, match: '2524475',
  base: { HEADER: { TEAM: [{ id: '1', pts: '0' }, { id: '2', pts: '0' }] }, BOXSCORE: { TEAM: [] }, PLAYBYPLAY: {}, SHOTCHART: {} },
  lines: [{ f: 0, l: { num: '1' } }], shots: [],
  frames: [{ t: 0, h: { status: '2', statusText: 'EN DIRECTO', quarter: 1, time: '09:50', pts: { '1': 0, '2': 0 } } }],
  gaps: {},
}
const tick = () => new Promise<void>(resolve => setTimeout(resolve, 5))

describe('during a match', () => {
  it('the notice is hidden while the live mode is connected and comes back when it stops', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 5
    mount(deps(), {
      store: store(), febHttp: feb.get, feedTiming: { intervalMs: 5, waitingIntervalMs: 5, tailPolls: 0, sleep: tick },
    })
    await screen.findByRole('status', { name: /actualización/i })
    fireEvent.click(await screen.findByRole('button', { name: /conectar/i }))
    await waitFor(() => expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull())
    fireEvent.click(await screen.findByRole('button', { name: /desconectar|detener/i }))
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i })).toBeTruthy())
  })
})
