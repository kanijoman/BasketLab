import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'
import type { PackageStore, StoredPackage } from '../package/storage'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}

const out = (elapsed: number, alerts: EngineOutput['alerts'] = []): EngineOutput => ({
  snapshot: { period: 1, remaining: 600 - elapsed, elapsed, score: { '1': elapsed, '2': elapsed - 1 } } as never,
  alerts,
  analysis: {},
})

const ALERT = {
  key: 'foul:9:3', id: 'foul_trouble', severity: 'critical' as const, category: 'faltas',
  message: 'J. PÉREZ: 4 faltas personales. Gestionar sus minutos.', evidence: {}, rearm_s: null,
  proposal: [{ type: 'sub', out_id: '9', out_name: 'J. PÉREZ', in_id: '10', in_name: 'L. GÓMEZ' }],
}

function fakeEngine(over: Partial<EngineApi> = {}): EngineApi {
  return {
    start: vi.fn().mockResolvedValue(META),
    loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
    replay: vi.fn(async (e: number) => out(e, e >= 5 ? [ALERT] : [])),
    update: vi.fn(),
    dispose: vi.fn(),
    ...over,
  }
}

const PKG_TEXT = JSON.stringify({
  checksum: 'x',
  package: {
    team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, season: '2025-2026',
    collection: 'c', created_at: '2026-10-08T12:00:00Z',
    tables: { players: { a: {} }, rival_players: { b: {} } }, baselines: { sample_games: { own: 5, rival: 4, league: 50 } },
  },
})

function memoryStore(initial: StoredPackage | null = null): PackageStore & { saved: StoredPackage | null } {
  const s = {
    saved: initial,
    load: async () => s.saved,
    save: async (r: StoredPackage) => { s.saved = r },
    clear: async () => { s.saved = null },
  }
  return s
}

const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })
const replayCalls = (e: EngineApi) => (e.replay as ReturnType<typeof vi.fn>).mock.calls

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  // the published-packages list must never reach the network from these tests
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

describe('App', () => {
  it('shows a loading state, then both teams once the engine is ready', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    expect(screen.getByText(/cargando motor/i)).toBeTruthy()
    expect(await screen.findByText('EQUIPO PROPIO')).toBeTruthy()
    expect(screen.getByText('EQUIPO RIVAL')).toBeTruthy()
  })

  it('reports an engine start failure to the user', async () => {
    render(<App engine={fakeEngine({ start: vi.fn().mockRejectedValue(new Error('checksum')) })} loadDemo={loadDemo} />)
    expect(await screen.findByText(/no se pudo iniciar el motor/i)).toBeTruthy()
    expect(screen.getByText(/checksum/)).toBeTruthy()
  })

  it('plays the demo: the clock advances and alerts with their proposal appear', async () => {
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    await waitFor(() => expect(screen.getByText(/4 faltas personales/)).toBeTruthy())
    expect(screen.getByText(/crítica/i)).toBeTruthy()
    expect(screen.getByText(/J\. PÉREZ → L\. GÓMEZ/)).toBeTruthy()
    expect(replayCalls(engine).length).toBeGreaterThan(0)
  })

  it('does not show the same alert twice', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    await waitFor(() => expect(screen.getAllByText(/4 faltas personales/)).toHaveLength(1))
    await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
    expect(screen.getAllByText(/4 faltas personales/)).toHaveLength(1)
  })

  it('lets the user change the replay speed', async () => {
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.change(screen.getByLabelText(/velocidad/i), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(replayCalls(engine).at(-1)![0]).toBeGreaterThanOrEqual(30)
  })

  it('stops at the end of the game', async () => {
    const engine = fakeEngine({ loadReplay: vi.fn().mockResolvedValue({ duration: 3, status: '' }) })
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    expect(screen.getByText(/partido finalizado/i)).toBeTruthy()
    const calls = replayCalls(engine).length
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(replayCalls(engine).length).toBe(calls)
  })

  describe('with an imported package', () => {
    const saved = { plaintext: PKG_TEXT, savedAt: '2026-10-09T10:00:00Z' }

    it('uses the stored package instead of the demo and shows its summary', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} loadDemo={loadDemo} store={memoryStore(saved)} />)
      expect(await screen.findByText(/partidos: 5 propios/)).toBeTruthy()
      expect(engine.start).toHaveBeenCalledWith(PKG_TEXT)
      expect(engine.loadReplay).not.toHaveBeenCalled()
      expect(screen.queryByRole('button', { name: /reproducir/i })).toBeNull()
      expect(screen.getByText(/en directo/i)).toBeTruthy()
    })

    it('goes back to the demo when the package is removed', async () => {
      const store = memoryStore(saved)
      render(<App engine={fakeEngine()} loadDemo={loadDemo} store={store} />)
      fireEvent.click(await screen.findByRole('button', { name: /quitar paquete/i }))
      expect(await screen.findByRole('button', { name: /reproducir/i })).toBeTruthy()
      expect(store.saved).toBeNull()
    })

    it('reports a stored package the engine rejects and offers to remove it', async () => {
      const engine = fakeEngine({ start: vi.fn().mockRejectedValue(new Error('Package schema version 9 is not supported')) })
      render(<App engine={engine} loadDemo={loadDemo} store={memoryStore(saved)} />)
      expect(await screen.findByText(/schema version 9/)).toBeTruthy()
      expect(screen.getByRole('button', { name: /quitar paquete/i })).toBeTruthy()
    })
  })
})
