import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { fakeEngine, loadDemo, memoryStore, META, out, PKG_TEXT, replayCalls } from './appTestKit'

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
    expect(screen.getAllByText(/crítica/i).length).toBeGreaterThan(0)
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
    fireEvent.click(screen.getByRole('radio', { name: '30×' }))
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(replayCalls(engine).at(-1)![0]).toBeGreaterThanOrEqual(30)
  })

  it('seeks forward on the timeline without restarting the engine (issue #231)', async () => {
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '60' } })
    await waitFor(() => expect(replayCalls(engine).at(-1)![0]).toBe(60))
    expect(engine.loadReplay).toHaveBeenCalledTimes(1)
    expect((screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement).value).toBe('60')
  })

  it('seeks back by rebuilding the engine from the start and jumping to that second (issue #231)', async () => {
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '60' } })
    await waitFor(() => expect(replayCalls(engine).at(-1)![0]).toBe(60))
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '20' } })
    await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(replayCalls(engine).at(-1)![0]).toBe(20))
    expect((screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement).value).toBe('20')
  })

  it('pauses when the user seeks (issue #231)', async () => {
    const engine = fakeEngine()
    render(<App engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    expect(screen.getByRole('button', { name: 'Pausa' })).toBeTruthy()
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '40' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reproducir' })).toBeTruthy())
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
      await screen.findByText('EQUIPO PROPIO')
      fireEvent.click(screen.getByRole('tab', { name: 'Paquetes' }))                   // the summary is in the Paquetes tab (#224)
      expect(await screen.findByText(/partidos: 5 propios/)).toBeTruthy()
      fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
      expect(engine.start).toHaveBeenCalledWith(PKG_TEXT)
      expect(engine.loadReplay).not.toHaveBeenCalled()
      expect(screen.queryByRole('button', { name: /reproducir/i })).toBeNull()
      expect(screen.getByText(/en directo/i)).toBeTruthy()
    })

    it('goes back to the demo when the package is removed', async () => {
      const store = memoryStore(saved)
      render(<App engine={fakeEngine()} loadDemo={loadDemo} store={store} />)
      await screen.findByText('EQUIPO PROPIO')
      fireEvent.click(screen.getByRole('tab', { name: 'Paquetes' }))
      fireEvent.click(await screen.findByRole('button', { name: /quitar paquete/i }))
      fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
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
