import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
    loadRecording: vi.fn().mockResolvedValue({ duration: 100, status: 'GRABACION', match: '2524470', frames: 10 }),
    // seconds 0-2: the match is not there yet; 3-5: FEB answers 404; afterwards the engine output (with an alert)
    playRecording: vi.fn(async (s: number) =>
      s < 3 ? { feed: 'waiting' as const, output: null }
        : s < 6 ? { feed: 'gap' as const, output: null }
          : { feed: 'ok' as const, output: out(s, s >= 8 ? [ALERT] : []) }),
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

const PACE = {
  reliable: true, possessions: 36, current40: 72, habit_own40: 70, habit_rival40: 62,
  delta_own: 2, delta_rival: 10, projected_possessions: 72.4, sample_games: { own: 4, rival: 3 },
}

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

  it('shows the pace card under the scoreboard once the engine reports the pace', async () => {
    const engine = fakeEngine({ replay: vi.fn(async (e: number) => ({ ...out(e), analysis: e >= 5 ? { pace: PACE } : {} })) })
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.getByText(/calculando/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    await waitFor(() => expect(screen.getByText('72,0')).toBeTruthy())
    expect(screen.getByText(/EQUIPO RIVAL/, { selector: '.pace-name' })).toBeTruthy()
  })

  describe('the most recently processed match is the default (issues #174, #223)', () => {
    const pick = (value: string) =>
      fireEvent.change(screen.getByLabelText(/partido de la demostración/i), { target: { value } })
    const MANIFEST = [{
      code: '2524470', title: 'Recoletas Zamora – Mipelletymas B.F. Leon', date: '2026-10-10T17:00',
      home: { id: '2', name: 'EQUIPO RIVAL' }, away: { id: '1', name: 'EQUIPO PROPIO' },
      recording: '2524470.recording.json', package: '2524470.package.json',
    }]
    const loadManifest = () => Promise.resolve(MANIFEST)
    const loadMatch = () => Promise.resolve({ package: 'REALPKG', recording: 'REC' })
    const props = { loadDemo, loadManifest, loadMatch }

    it('opens on the latest recorded match, not on the sample game', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} {...props} />)
      await waitFor(() => expect(engine.loadRecording).toHaveBeenCalledWith('REC'))
      expect(engine.start).toHaveBeenLastCalledWith('REALPKG')
      expect(engine.loadReplay).not.toHaveBeenCalled()
      const select = await screen.findByLabelText(/partido de la demostración/i) as HTMLSelectElement
      expect(select.value).toBe('2524470')
      expect(within(select).getAllByRole('option').map(o => o.textContent))
        .toEqual(['Recoletas Zamora – Mipelletymas B.F. Leon', 'Partido de ejemplo'])
    })

    it('plays it second by second: waits for the match, shows the real 404 and then the alerts', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} {...props} />)
      fireEvent.click(await screen.findByRole('button', { name: /reproducir/i }))
      await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
      expect(await screen.findByText(/esperando el inicio/i)).toBeTruthy()
      await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
      expect(await screen.findByText(/FEB no responde/i)).toBeTruthy()
      await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
      await waitFor(() => expect(screen.getByText(/J\. PÉREZ: 4 faltas/)).toBeTruthy())
      expect(screen.queryByText(/FEB no responde/i)).toBeNull()
      expect(engine.replay).not.toHaveBeenCalled() // the recording goes through playRecording, not the truncated replay
    })

    it('puts the local team on the left of the scoreboard (home id from the engine metadata)', async () => {
      const engine = fakeEngine({ start: vi.fn().mockResolvedValue({ ...META, home_id: '2' }) })
      render(<App engine={engine} {...props} />)
      await screen.findByLabelText(/partido de la demostración/i)
      const sides = Array.from(document.querySelectorAll('.scoreboard .team .name')).map(n => n.textContent)
      expect(sides).toEqual(['EQUIPO RIVAL', 'EQUIPO PROPIO'])
    })

    it('without any recording it falls back to the sample game', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} loadMatch={loadMatch} />)
      await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledWith('GAME'))
      expect(engine.loadRecording).not.toHaveBeenCalled()
    })

    it('a manifest that cannot be read also falls back to the sample game', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} loadDemo={loadDemo} loadManifest={() => Promise.reject(new Error('404'))} loadMatch={loadMatch} />)
      await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledWith('GAME'))
    })

    it('switches to the sample game and back to the recorded match', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} {...props} />)
      await waitFor(() => expect(engine.loadRecording).toHaveBeenCalledTimes(1))
      pick('sample')
      await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith('PKG'))
      expect(engine.loadReplay).toHaveBeenLastCalledWith('GAME')
      pick('2524470')
      await waitFor(() => expect(engine.loadRecording).toHaveBeenCalledTimes(2))
    })

    it('says so and shows the sample game when the recording cannot be loaded', async () => {
      const engine = fakeEngine()
      render(<App engine={engine} loadDemo={loadDemo} loadManifest={loadManifest} loadMatch={() => Promise.reject(new Error('sin red'))} />)
      expect(await screen.findByText(/no se pudo cargar el partido/i)).toBeTruthy()
      expect(engine.loadReplay).toHaveBeenCalledWith('GAME')
    })
  })
})
