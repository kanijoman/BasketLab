// Live mode of the app (issue #217): a loaded package + "Conectar con FEB" -> the feed client polls FEB and the
// engine is fed with the merged documents; alerts and the connection status show up.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import type { PackageStore, StoredPackage } from '../package/storage'
import { memoryFinishedStore, type FinishedMatch } from '../feed/finishedStore'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}

const out = (alerts: EngineOutput['alerts'] = []): EngineOutput => ({
  snapshot: { period: 1, remaining: 593, elapsed: 7, score: { '1': 2, '2': 0 } } as never,
  alerts,
  analysis: {},
})

const ALERT = {
  key: 'foul:9:3', id: 'foul_trouble', severity: 'critical' as const, category: 'faltas',
  message: 'J. PÉREZ: 4 faltas personales. Gestionar sus minutos.', evidence: {}, rearm_s: null, proposal: [],
}

function fakeEngine(over: Partial<EngineApi> = {}): EngineApi {
  return {
    start: vi.fn().mockResolvedValue(META),
    loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
    replay: vi.fn(),
    update: vi.fn(async () => out()),
    loadRecording: vi.fn(),
    playRecording: vi.fn(),
    setMode: vi.fn().mockResolvedValue(undefined),
    dispose: vi.fn(),
    ...over,
  }
}

const PKG = JSON.stringify({
  checksum: 'x',
  package: {
    team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, season: '2025-2026',
    collection: 'c', created_at: '2026-10-08T12:00:00Z', tables: { players: {}, rival_players: {} },
    baselines: { sample_games: { own: 5, rival: 4, league: 50 } },
    competition_meta: { match: { code: '2524475' } },
  },
})
const SAVED: StoredPackage = { plaintext: PKG, savedAt: '2026-10-09T10:00:00Z' }

function memoryStore(): PackageStore {
  let saved: StoredPackage | null = SAVED
  return { load: async () => saved, save: async r => { saved = r }, clear: async () => { saved = null } }
}

const pack: Pack = {
  v: 1, match: '2524475',
  base: { HEADER: { TEAM: [{ id: '1', pts: '0' }, { id: '2', pts: '0' }] }, BOXSCORE: { TEAM: [] }, PLAYBYPLAY: {}, SHOTCHART: {} },
  lines: [{ f: 0, l: { num: '1' } }], shots: [],
  frames: [
    { t: 0, h: { status: '2', statusText: 'EN DIRECTO', quarter: 1, time: '09:50', pts: { '1': 0, '2': 0 } } },
    { t: 10, h: { status: '3', statusText: 'FINALIZADO', quarter: 4, time: 'FINAL', pts: { '1': 2, '2': 0 } } },
  ],
  gaps: {},
}
// a real (tiny) wait: an instantly-resolving sleep would never let the event loop breathe while the feed retries
const tick = () => new Promise<void>(resolve => setTimeout(resolve, 5))
const instant = { intervalMs: 5, waitingIntervalMs: 5, tailPolls: 0, sleep: tick }
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})

describe('live mode with a package', () => {
  it('connects to the match of the package, feeds the engine with the merged FEB documents and shows the alerts', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10 // already over: the first round brings the final document
    const engine = fakeEngine({ update: vi.fn(async () => out([ALERT])) })
    render(<App engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/J\. PÉREZ: 4 faltas/)).toBeTruthy()
    expect(engine.start).toHaveBeenLastCalledWith(PKG) // a fresh engine session for the match
    const doc = JSON.parse((engine.update as ReturnType<typeof vi.fn>).mock.calls[0][0])
    expect(Object.keys(doc)).toEqual(expect.arrayContaining(['HEADER', 'BOXSCORE', 'PLAYBYPLAY', 'SHOTCHART']))
    expect(feb.requests.some(r => r.url.endsWith('/partido/2524475'))).toBe(true)
    await waitFor(() => expect(screen.getByText(/partido finalizado/i)).toBeTruthy())
  })

  it('presents a burst of alerts one by one instead of in a block (issue #375)', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const burst = ['uno', 'dos', 'tres'].map(k => ({ ...ALERT, key: `burst:${k}`, severity: 'warning' as const, message: `Aviso ${k}` }))
    const engine = fakeEngine({ update: vi.fn(async () => out(burst)) })
    render(<App engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} alertCooldownMs={150} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))

    expect(await screen.findByText('Aviso uno')).toBeTruthy()
    expect(screen.queryByText('Aviso tres')).toBeNull()                // the others wait their turn
    expect(await screen.findByText('Aviso tres', {}, { timeout: 3000 })).toBeTruthy()
    expect(screen.getAllByText('Aviso uno')).toHaveLength(1)           // nothing is shown twice
  })

  it('a critical alert of the burst is not made to wait (issue #375)', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const burst = [{ ...ALERT, key: 'burst:w', severity: 'warning' as const, message: 'Aviso previo' }, ALERT]
    const engine = fakeEngine({ update: vi.fn(async () => out(burst)) })
    render(<App engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} alertCooldownMs={2000} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))

    expect(await screen.findByText(/J\. PÉREZ: 4 faltas/)).toBeTruthy()   // at once, before the 2 s cooldown
    expect(screen.queryByText('Aviso previo')).toBeNull()
  })

  it('shows the score and the clock coming from the engine', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await waitFor(() => expect(engine.update).toHaveBeenCalled())
    expect(await screen.findByText('Q1 09:53')).toBeTruthy()
  })

  it('keeps waiting before the match and disconnects on demand', async () => {
    const feb = new FakeFeb(pack)
    feb.at = -100 // not started: FEB answers 404
    const slow = { ...instant, sleep: () => new Promise<void>(resolve => setTimeout(resolve, 20)) }
    render(<App engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={slow} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/esperando el inicio del partido/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    await waitFor(() => expect(screen.getByRole('button', { name: /conectar con feb/i })).toBeTruthy())
  })

  it('reports a failure of the engine on a document without stopping the feed', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    const engine = fakeEngine({ update: vi.fn().mockRejectedValue(new Error('boom')) })
    render(<App engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={{ ...instant, tailPolls: 0 }} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    expect(await screen.findByText(/boom/)).toBeTruthy()
  })
})

// #407: a finished live match is kept on the device and can be reviewed afterwards
describe('finished matches (issue #407)', () => {
  const connectAndFinish = async (finishedStore = memoryFinishedStore(), engine = fakeEngine()) => {
    const feb = new FakeFeb(pack)
    feb.at = 10
    render(<App engine={engine} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} finishedStore={finishedStore} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await waitFor(() => expect(screen.getByText(/^partido finalizado$/i)).toBeTruthy())
    return { finishedStore, engine }
  }

  it('saves the match when the feed ends, with the package and the last document, and offers to review it', async () => {
    const { finishedStore } = await connectAndFinish()
    await waitFor(async () => expect((await finishedStore.list()).map(m => m.code)).toEqual(['2524475']))
    const saved = (await finishedStore.load('2524475')) as FinishedMatch
    expect(saved.plaintext).toBe(PKG)
    expect(saved.title).toBe('EQUIPO PROPIO – EQUIPO RIVAL')
    expect(Object.keys(JSON.parse(saved.game))).toEqual(expect.arrayContaining(['HEADER', 'PLAYBYPLAY', 'SHOTCHART']))
    expect(await screen.findByRole('button', { name: /revisar equipo propio – equipo rival/i })).toBeTruthy()
  })

  it('reviewing it replays the saved document with the saved package, and the package match can be recovered', async () => {
    const engine = fakeEngine()
    const { finishedStore } = await connectAndFinish(memoryFinishedStore(), engine)
    const saved = await waitFor(async () => { const m = await finishedStore.load('2524475'); if (!m) throw new Error('not yet'); return m })
    fireEvent.click(await screen.findByRole('button', { name: /revisar equipo propio – equipo rival/i }))
    await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledWith(saved.game))
    expect(engine.start).toHaveBeenLastCalledWith(saved.plaintext)
    expect(await screen.findByText(/estás revisando un partido/i)).toBeTruthy()
  })

  it('the matches saved in earlier sessions are listed from the start', async () => {
    const old: FinishedMatch = { code: '9', title: 'LEON – UNIBASKET', savedAt: '2026-10-17T20:30:00Z', plaintext: PKG, game: '{"PLAYBYPLAY":{"LINES":[]}}' }
    render(<App engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={new FakeFeb(pack).get} feedTiming={instant}
      finishedStore={memoryFinishedStore([old])} />)
    expect(await screen.findByRole('button', { name: /revisar leon – unibasket/i })).toBeTruthy()
  })

  it('a match that did not reach its end is not saved', async () => {
    const feb = new FakeFeb(pack)
    feb.at = 0
    const finishedStore = memoryFinishedStore()
    render(<App engine={fakeEngine()} loadDemo={loadDemo} store={memoryStore()} febHttp={feb.get} feedTiming={instant} finishedStore={finishedStore} />)
    fireEvent.click(await screen.findByRole('button', { name: /conectar con feb/i }))
    await screen.findByText(/en directo/i)
    fireEvent.click(screen.getByRole('button', { name: /desconectar/i }))
    expect(await finishedStore.list()).toEqual([])
  })
})
