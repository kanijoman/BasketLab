// The update notice of the build for Google Play (issue #1043): asked to Play on opening and on coming back to the foreground, a flexible download in the
// background, «restart to install», a clear message when Play does not see the release, and none of it during a match.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { AppUpdateDeps } from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import type { AppVersion } from '../about/appInfo'
import type { PlayInfo, PlayInstall, PlayUpdater } from '../about/playUpdate'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import type { PackageStore, StoredPackage } from '../package/storage'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })
const engine = (): EngineApi => ({
  start: vi.fn().mockResolvedValue(META),
  loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
  replay: vi.fn(), update: vi.fn(async (): Promise<EngineOutput> => ({
    snapshot: { period: 1, remaining: 593, elapsed: 7, score: { '1': 2, '2': 0 } } as never, alerts: [], analysis: {},
  })),
  loadRecording: vi.fn(), playRecording: vi.fn(), report: vi.fn(), beginRecording: vi.fn(), recordGap: vi.fn(), updateStreaming: vi.fn(), updateFbcylFinal: vi.fn(), lastDocument: vi.fn(), recording: vi.fn(), setMode: vi.fn(), dispose: vi.fn(),
})
function memory() {
  const data = new Map<string, string>()
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => { data.set(k, v) }, removeItem: (k: string) => { data.delete(k) } }
}

const PLAY: AppVersion = { name: '0.7.0', build: 70, builtAt: null, native: true, distribution: 'play' }
const LATEST = { version: '0.8.0', versionCode: 80, apk: 'https://example.test/basketlab-live.apk', notes: null, built_at: null }
const info = (over: Partial<PlayInfo> = {}): PlayInfo => ({ availability: 'none', installStatus: 'unknown', availableCode: null, flexibleAllowed: true, ...over })

/** A Play that the test drives: what it answers, what the user pressed, and the download progress it announces. */
function fakePlay(answer: PlayInfo | Error = info()) {
  let listener: ((s: { install: PlayInstall; percent: number | null }) => void) | null = null
  const updater: PlayUpdater = {
    getInfo: vi.fn(async () => { if (answer instanceof Error) throw answer; return answer }),
    startFlexible: vi.fn(async () => 'ok' as const),
    complete: vi.fn(async () => undefined),
    onStatus: vi.fn(async cb => { listener = cb; return () => { listener = null } }),
  }
  return { updater, answer: (next: PlayInfo | Error) => { answer = next }, emit: (s: { install: PlayInstall; percent: number | null }) => listener?.(s) }
}

function deps(play: ReturnType<typeof fakePlay>, over: Partial<AppUpdateDeps> = {}, version: AppVersion = PLAY, latest: unknown = LATEST): AppUpdateDeps {
  return {
    getInstalled: async () => version, fetchJson: vi.fn().mockResolvedValue(latest), openUrl: vi.fn(), storage: memory(),
    play: { updater: () => play.updater },
    ...over,
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})

const openAbout = () => fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
const mount = (d: AppUpdateDeps, extra: object = {}) =>
  render(<App initialTab="partido" engine={engine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} appUpdate={d} {...extra} />)
const notice = () => screen.findByRole('status', { name: /actualización/i })

describe('a version that Play offers', () => {
  it('is noticed on opening, downloaded in the background from its button and installed with a restart', async () => {
    const play = fakePlay(info({ availability: 'available', availableCode: 80 }))
    mount(deps(play))
    await screen.findByText('EQUIPO PROPIO')
    expect((await notice()).textContent).toMatch(/hay una versión nueva en google play/i)
    fireEvent.click(screen.getByRole('button', { name: 'Descargar' }))
    await waitFor(() => expect(play.updater.startFlexible).toHaveBeenCalledTimes(1))
    expect((await notice()).textContent).toMatch(/descargando la versión nueva/i)
    await waitFor(() => expect(play.updater.onStatus).toHaveBeenCalled())
    play.emit({ install: 'downloading', percent: 40 })
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i }).textContent).toMatch(/40 ?%/))
    play.emit({ install: 'downloaded', percent: 100 })
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i }).textContent).toMatch(/reinicia la app para instalarla/i))
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar e instalar' }))
    await waitFor(() => expect(play.updater.complete).toHaveBeenCalledTimes(1))
  })

  it('the user who declines the system dialog goes back to «available», not to an error', async () => {
    const play = fakePlay(info({ availability: 'available', availableCode: 80 }))
    vi.mocked(play.updater.startFlexible).mockResolvedValueOnce('canceled')
    mount(deps(play))
    await notice()
    fireEvent.click(screen.getByRole('button', { name: 'Descargar' }))
    await waitFor(() => expect(play.updater.startFlexible).toHaveBeenCalled())
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i }).textContent).toMatch(/hay una versión nueva en google play/i))
  })

  it('a download that fails says so and can be tried again', async () => {
    const play = fakePlay(info({ availability: 'available', availableCode: 80 }))
    vi.mocked(play.updater.startFlexible).mockResolvedValueOnce('failed')
    mount(deps(play))
    await notice()
    fireEvent.click(screen.getByRole('button', { name: 'Descargar' }))
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i }).textContent).toMatch(/no ha podido descargar/i))
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(play.updater.startFlexible).toHaveBeenCalledTimes(2))
  })

  it('Acerca de has the same text and the same button as the notice', async () => {
    const play = fakePlay(info({ availability: 'available', availableCode: 80 }))
    mount(deps(play))
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    expect((await screen.findAllByText(/hay una versión nueva en google play/i)).length).toBe(2)          // the notice and Acerca de
    expect(screen.queryByText(/se actualiza desde google play/i)).toBeNull()
    fireEvent.click(screen.getAllByRole('button', { name: 'Descargar' })[0])
    await waitFor(() => expect(play.updater.startFlexible).toHaveBeenCalledTimes(1))
  })
})

describe('a release that Play does not offer to this tablet', () => {
  it('says which version is published and how to reach it, in the notice and in Acerca de', async () => {
    const play = fakePlay(info())
    mount(deps(play))
    expect((await notice()).textContent).toMatch(/versión 0\.8\.0 ya está publicada.*no se la ofrece a esta tablet/i)
    expect(screen.getByRole('status', { name: /actualización/i }).textContent).toContain('es.basketlab.live (unreviewed)')
    openAbout()
    expect(screen.getAllByText(/enlace de pruebas internas/i).length).toBeGreaterThan(0)
  })

  it('nothing published newer than the installed build, nothing said; Acerca de says it is the latest', async () => {
    const play = fakePlay(info())
    mount(deps(play, {}, PLAY, { ...LATEST, versionCode: 70 }))
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    expect(await screen.findByText(/tienes la última versión/i)).toBeTruthy()
    expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull()
  })
})

describe('when Play is asked', () => {
  it('asks again on coming back to the foreground, at most once every few minutes', async () => {
    let resume: (() => void) | null = null
    let now = 1_000_000
    const play = fakePlay(info())
    mount(deps(play, { play: { updater: () => play.updater, now: () => now, onResume: cb => { resume = cb; return () => { resume = null } } } }, PLAY, { ...LATEST, versionCode: 70 }))
    await screen.findByText('EQUIPO PROPIO')
    await waitFor(() => expect(play.updater.getInfo).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(resume).not.toBeNull())
    resume!()                                                            // two minutes later: not again
    now += 2 * 60 * 1000
    await new Promise(r => setTimeout(r, 20))
    expect(play.updater.getInfo).toHaveBeenCalledTimes(1)
    play.answer(info({ availability: 'available', availableCode: 80 }))
    now += 9 * 60 * 1000                                                 // the release arrived on Play meanwhile
    resume!()
    expect((await notice()).textContent).toMatch(/hay una versión nueva en google play/i)
    expect(play.updater.getInfo).toHaveBeenCalledTimes(2)
  })

  it('the button of Acerca de asks again at once', async () => {
    const play = fakePlay(info())
    mount(deps(play, {}, PLAY, { ...LATEST, versionCode: 70 }))
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    await screen.findByText(/tienes la última versión/i)
    play.answer(info({ availability: 'available', availableCode: 80 }))
    fireEvent.click(screen.getByRole('button', { name: /buscar actualización/i }))
    expect((await screen.findAllByText(/hay una versión nueva en google play/i)).length).toBeGreaterThan(0)
  })

  it('Play that does not answer is said in Acerca de and never in the notice', async () => {
    const play = fakePlay(new Error('no Play services'))
    mount(deps(play))
    await screen.findByText('EQUIPO PROPIO')
    openAbout()
    expect(await screen.findByText(/no se pudo consultar google play/i)).toBeTruthy()
    expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull()
  })

  it('the APK build never asks Play: the updater is not even created', async () => {
    const play = fakePlay(info({ availability: 'available', availableCode: 80 }))
    const make = vi.fn(() => play.updater)
    mount(deps(play, { play: { updater: make } }, { name: '0.7.0', build: 70, builtAt: null, native: true }))
    await screen.findByText('EQUIPO PROPIO')
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i })).toBeTruthy())      // the APK notice of #227, not Play's
    expect(make).not.toHaveBeenCalled()
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
  it('the notice is hidden while the live mode is connected, the buttons of Acerca de wait, and it all comes back when it stops', async () => {
    const play = fakePlay(info({ availability: 'available', availableCode: 80 }))
    const feb = new FakeFeb(pack)
    feb.at = 5
    mount(deps(play), { store: store(), febHttp: feb.get, feedTiming: { intervalMs: 5, waitingIntervalMs: 5, tailPolls: 0, sleep: tick } })
    await notice()
    fireEvent.click(await screen.findByRole('button', { name: /conectar/i }))
    await waitFor(() => expect(screen.queryByRole('status', { name: /actualización/i })).toBeNull())
    openAbout()
    const wait = await screen.findByRole('button', { name: 'Descargar' })
    expect(wait).toBeDisabled()                                          // not now: the system dialog and the restart would interrupt the match
    expect(screen.getByText(/cuando acabe el partido/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
    fireEvent.click(await screen.findByRole('button', { name: /desconectar|detener/i }))
    await waitFor(() => expect(screen.getByRole('status', { name: /actualización/i })).toBeTruthy())
  })
})
