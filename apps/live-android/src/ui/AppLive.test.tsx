// Live mode of the app (issue #217): a loaded package + "Conectar con FEB" -> the feed client polls FEB and the
// engine is fed with the merged documents; alerts and the connection status show up.
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import { FakeFeb, type Pack } from '../feed/fakeFeb'
import type { PackageStore, StoredPackage } from '../package/storage'

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
