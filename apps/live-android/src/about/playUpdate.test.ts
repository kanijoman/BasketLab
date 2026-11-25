// The update notice of the build for Google Play (issue #1043): Play's in-app update API (flexible), the states it can be in, their texts in Spanish,
// and a plugin that only the Play build ever loads.
import { describe, expect, it, vi } from 'vitest'
import type { AppVersion } from './appInfo'
import { parseLatest } from './update'
import { createNativeUpdater, playUpdateText, resolvePlayUpdate, type PlayInfo, type PlayUpdater } from './playUpdate'

const PLAY: AppVersion = { name: '0.7.0', build: 70, builtAt: null, native: true, distribution: 'play' }
const APK: AppVersion = { name: '0.7.0', build: 70, builtAt: null, native: true }
const LATEST = parseLatest({ version: '0.8.0', versionCode: 80, apk: 'https://example.test/basketlab-live.apk' })!

const info = (over: Partial<PlayInfo> = {}): PlayInfo => ({ availability: 'none', installStatus: 'unknown', availableCode: null, flexibleAllowed: true, ...over })
const updater = (answer: PlayInfo | Error): PlayUpdater => ({
  getInfo: vi.fn(async () => { if (answer instanceof Error) throw answer; return answer }),
  startFlexible: vi.fn(async () => 'ok' as const), complete: vi.fn(async () => undefined), onStatus: vi.fn(async () => () => undefined),
})
const resolve = (answer: PlayInfo | Error, latest: typeof LATEST | null = null, installed: AppVersion | null = PLAY) =>
  resolvePlayUpdate({ installed, updater: () => updater(answer), latest: async () => latest })

describe('what Play says about the installed build', () => {
  it('a version Play offers is available, with its build number', async () => {
    expect(await resolve(info({ availability: 'available', availableCode: 80 }))).toEqual({ status: 'available', versionCode: 80 })
  })

  it('no newer version anywhere is up to date', async () => {
    expect(await resolve(info())).toEqual({ status: 'up_to_date' })
  })

  it('a download in progress is downloading, and a finished one is downloaded: restart to install', async () => {
    expect(await resolve(info({ availability: 'in_progress', installStatus: 'downloading' }))).toEqual({ status: 'downloading', percent: null })
    expect(await resolve(info({ availability: 'in_progress', installStatus: 'downloaded' }))).toEqual({ status: 'downloaded' })
    expect(await resolve(info({ availability: 'none', installStatus: 'downloaded' }))).toEqual({ status: 'downloaded' })    // restarted without installing: Play still has it ready
  })

  it('Play that does not answer, or answers «unknown», is unknown: never an invented state', async () => {
    expect(await resolve(new Error('Play services missing'))).toEqual({ status: 'unknown' })
    expect(await resolve(info({ availability: 'unknown' }))).toEqual({ status: 'unknown' })
  })

  it('a release published (latest.json) that Play does not offer to this tablet is said, with the version', async () => {
    expect(await resolve(info(), LATEST)).toEqual({ status: 'not_offered', latest: LATEST })
  })

  it('the published one is not newer than the installed build: nothing to say; a rolled-back release never nags', async () => {
    expect(await resolve(info(), { ...LATEST, versionCode: 70 })).toEqual({ status: 'up_to_date' })
    expect(await resolve(info(), { ...LATEST, versionCode: 60 })).toEqual({ status: 'up_to_date' })
    expect(await resolve(info(), LATEST, { ...PLAY, build: null })).toEqual({ status: 'up_to_date' })      // an unknown build never nags
  })

  it('Play offering the update wins over latest.json: the answer of the store is the one that matters', async () => {
    expect(await resolve(info({ availability: 'available', availableCode: 80 }), LATEST)).toEqual({ status: 'available', versionCode: 80 })
  })

  it('the APK build and the browser never ask Play: «unsupported» and the plugin is not even created', async () => {
    const make = vi.fn(() => updater(info()))
    expect(await resolvePlayUpdate({ installed: APK, updater: make, latest: async () => null })).toEqual({ status: 'unsupported' })
    expect(await resolvePlayUpdate({ installed: { ...PLAY, native: false }, updater: make, latest: async () => null })).toEqual({ status: 'unsupported' })
    expect(await resolvePlayUpdate({ installed: null, updater: make, latest: async () => null })).toEqual({ status: 'unsupported' })
    expect(make).not.toHaveBeenCalled()
  })

  it('a latest.json that cannot be read does not break the answer of Play', async () => {
    const state = await resolvePlayUpdate({ installed: PLAY, updater: () => updater(info()), latest: async () => { throw new Error('offline') } })
    expect(state).toEqual({ status: 'up_to_date' })
  })
})

describe('the texts of each state (Spanish)', () => {
  it.each([
    [{ status: 'available', versionCode: 80 } as const, /hay una versión nueva en google play/i, 'Descargar'],
    [{ status: 'downloading', percent: 40 } as const, /descargando.*40 ?%/i, null],
    [{ status: 'downloading', percent: null } as const, /descargando la versión nueva/i, null],
    [{ status: 'downloaded' } as const, /descargada.*reinicia/i, 'Reiniciar e instalar'],
    [{ status: 'up_to_date' } as const, /tienes la última versión/i, null],
    [{ status: 'unknown' } as const, /no se pudo consultar google play/i, null],
    [{ status: 'error', reason: 'failed' } as const, /no ha podido descargar/i, 'Reintentar'],
    [{ status: 'error', reason: 'not_allowed' } as const, /no permite actualizar sin salir de la app/i, null],
  ])('%j', (state, text, action) => {
    const said = playUpdateText(state)
    expect(said.text).toMatch(text)
    expect(said.action).toBe(action)
  })

  it('a version that is published but not offered says how to reach it while the store listing is not reviewed (temporary name, testers link)', () => {
    const said = playUpdateText({ status: 'not_offered', latest: LATEST })
    expect(said.text).toContain('0.8.0')
    expect(said.text).toMatch(/google play no se la ofrece a esta tablet/i)
    expect(said.text).toContain('es.basketlab.live (unreviewed)')
    expect(said.text).toMatch(/enlace de pruebas internas/i)
    expect(said.text).toMatch(/quien administra/i)
    expect(said.action).toBeNull()
  })

  it('unsupported has no text at all', () => {
    expect(playUpdateText({ status: 'unsupported' })).toEqual({ text: null, action: null })
  })
})

describe('the plugin of Play behind its own interface (a fake plugin, no Play in the tests)', () => {
  type Listener = (s: { installStatus: number; bytesDownloaded?: number; totalBytesToDownload?: number }) => void
  const fakePlugin = (over: Record<string, unknown> = {}) => {
    const listeners: Listener[] = []
    const plugin = {
      getAppUpdateInfo: vi.fn(async () => ({ currentVersionCode: '70', availableVersionCode: '80', updateAvailability: 2, flexibleUpdateAllowed: true, installStatus: 0 })),
      startFlexibleUpdate: vi.fn(async () => ({ code: 0 })),
      completeFlexibleUpdate: vi.fn(async () => undefined),
      addListener: vi.fn(async (_event: string, cb: Listener) => { listeners.push(cb); return { remove: async () => { listeners.length = 0 } } }),
      ...over,
    }
    return { plugin, emit: (s: Parameters<Listener>[0]) => listeners.forEach(l => l(s)), listeners }
  }

  it('translates what the plugin returns into the states of the app', async () => {
    const { plugin } = fakePlugin()
    expect(await createNativeUpdater(() => Promise.resolve(plugin as never)).getInfo()).toEqual({ availability: 'available', installStatus: 'unknown', availableCode: 80, flexibleAllowed: true })
    const none = fakePlugin({ getAppUpdateInfo: async () => ({ currentVersionCode: '70', updateAvailability: 1, installStatus: 11 }) })
    expect(await createNativeUpdater(() => Promise.resolve(none.plugin as never)).getInfo()).toEqual({ availability: 'none', installStatus: 'downloaded', availableCode: null, flexibleAllowed: false })
  })

  it.each([[0, 'ok'], [1, 'canceled'], [2, 'failed'], [3, 'not_available'], [4, 'not_allowed'], [5, 'failed']])('the result code %i of starting the flexible update is «%s»', async (code, expected) => {
    const { plugin } = fakePlugin({ startFlexibleUpdate: async () => ({ code }) })
    expect(await createNativeUpdater(() => Promise.resolve(plugin as never)).startFlexible()).toBe(expected)
  })

  it('reports the progress of the download in percent and stops listening when told to', async () => {
    const { plugin, emit, listeners } = fakePlugin()
    const seen: Array<{ install: string; percent: number | null }> = []
    const stop = await createNativeUpdater(() => Promise.resolve(plugin as never)).onStatus(s => seen.push(s))
    emit({ installStatus: 2, bytesDownloaded: 25, totalBytesToDownload: 100 })
    emit({ installStatus: 2 })
    emit({ installStatus: 11 })
    expect(seen).toEqual([{ install: 'downloading', percent: 25 }, { install: 'downloading', percent: null }, { install: 'downloaded', percent: 100 }])
    stop()
    await Promise.resolve()
    expect(listeners).toHaveLength(0)
  })

  it('the restart is the complete call of the plugin, and the plugin is loaded once and only when something asks for it', async () => {
    const { plugin } = fakePlugin()
    const load = vi.fn(() => Promise.resolve(plugin as never))
    const native = createNativeUpdater(load)
    expect(load).not.toHaveBeenCalled()
    await native.getInfo()
    await native.complete()
    expect(plugin.completeFlexibleUpdate).toHaveBeenCalledTimes(1)
    expect(load).toHaveBeenCalledTimes(1)
  })
})
