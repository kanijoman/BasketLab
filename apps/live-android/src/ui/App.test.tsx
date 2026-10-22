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
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    expect(screen.getByText(/cargando motor/i)).toBeTruthy()
    expect(await screen.findByText('EQUIPO PROPIO')).toBeTruthy()
    expect(screen.getByText('EQUIPO RIVAL')).toBeTruthy()
  })

  it('reports an engine start failure to the user', async () => {
    render(<App initialTab="partido" engine={fakeEngine({ start: vi.fn().mockRejectedValue(new Error('checksum')) })} loadDemo={loadDemo} />)
    expect(await screen.findByText(/no se pudo iniciar el motor/i)).toBeTruthy()
    expect(screen.getByText(/checksum/)).toBeTruthy()
  })

  it('plays the demo: the clock advances and alerts with their proposal appear', async () => {
    const engine = fakeEngine()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    await waitFor(() => expect(screen.getByText(/4 faltas personales/)).toBeTruthy())
    expect(screen.getAllByText(/crítica/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/J\. PÉREZ → L\. GÓMEZ/)).toBeTruthy()
    expect(replayCalls(engine).length).toBeGreaterThan(0)
  })

  it('does not show the same alert twice', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    await waitFor(() => expect(screen.getAllByText(/4 faltas personales/)).toHaveLength(1))
    await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
    expect(screen.getAllByText(/4 faltas personales/)).toHaveLength(1)
  })

  it('lets the user change the replay speed', async () => {
    const engine = fakeEngine()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('radio', { name: '30×' }))
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(2100) })
    expect(replayCalls(engine).at(-1)![0]).toBeGreaterThanOrEqual(30)
  })

  it('seeks forward on the timeline without restarting the engine (issue #231)', async () => {
    const engine = fakeEngine()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '60' } })
    fireEvent.pointerUp(screen.getByRole('slider', { name: 'Línea de tiempo' }))     // the timeline seeks when it is released (issue #309)
    await waitFor(() => expect(replayCalls(engine).at(-1)![0]).toBe(60))
    expect(engine.loadReplay).toHaveBeenCalledTimes(1)
    expect((screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement).value).toBe('60')
  })

  it('seeks back by rebuilding the engine from the start and jumping to that second (issue #231)', async () => {
    const engine = fakeEngine()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '60' } })
    fireEvent.pointerUp(screen.getByRole('slider', { name: 'Línea de tiempo' }))
    await waitFor(() => expect(replayCalls(engine).at(-1)![0]).toBe(60))
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '20' } })
    fireEvent.pointerUp(screen.getByRole('slider', { name: 'Línea de tiempo' }))
    fireEvent.click(screen.getByRole('button', { name: /^saltar$/i }))     // going back asks first (issue #309)
    await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(replayCalls(engine).at(-1)![0]).toBe(20))
    expect((screen.getByRole('slider', { name: 'Línea de tiempo' }) as HTMLInputElement).value).toBe('20')
  })

  it('pauses when the user seeks (issue #231)', async () => {
    const engine = fakeEngine()
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    expect(screen.getByRole('button', { name: 'Pausa' })).toBeTruthy()
    fireEvent.change(screen.getByRole('slider', { name: 'Línea de tiempo' }), { target: { value: '40' } })
    fireEvent.pointerUp(screen.getByRole('slider', { name: 'Línea de tiempo' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reproducir' })).toBeTruthy())
  })

  it('stops at the end of the game', async () => {
    const engine = fakeEngine({ loadReplay: vi.fn().mockResolvedValue({ duration: 3, status: '' }) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
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
      render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore(saved)} />)
      await screen.findByText('EQUIPO PROPIO')
      fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))                   // the summary is in the Partidos tab (#224)
      expect(await screen.findByText(/partidos: 5 propios/)).toBeTruthy()
      fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
      expect(engine.start).toHaveBeenCalledWith(PKG_TEXT)
      expect(engine.loadReplay).not.toHaveBeenCalled()
      expect(screen.queryByRole('button', { name: /reproducir/i })).toBeNull()
      expect(screen.getByText(/en directo/i)).toBeTruthy()
    })

    it('goes back to the demo when the package is removed', async () => {
      const store = memoryStore(saved)
      render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} store={store} />)
      await screen.findByText('EQUIPO PROPIO')
      fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
      fireEvent.click(await screen.findByRole('button', { name: /quitar paquete/i }))
      fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
      expect(await screen.findByRole('button', { name: /reproducir/i })).toBeTruthy()
      expect(store.saved).toBeNull()
    })

    it('reports a stored package the engine rejects and offers to remove it', async () => {
      const engine = fakeEngine({ start: vi.fn().mockRejectedValue(new Error('Package schema version 9 is not supported')) })
      render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} store={memoryStore(saved)} />)
      expect(await screen.findByText(/schema version 9/)).toBeTruthy()
      expect(screen.getByRole('button', { name: /quitar paquete/i })).toBeTruthy()
    })
  })

  it('shows the pace card under the scoreboard once the engine reports the pace', async () => {
    const engine = fakeEngine({ replay: vi.fn(async (e: number) => ({ ...out(e), analysis: e >= 5 ? { pace: PACE } : {} })) })
    render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    expect(screen.getByText(/calculando/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000) })
    await waitFor(() => expect(screen.getByText('72,0')).toBeTruthy())
    expect(screen.getByText(/EQUIPO RIVAL/, { selector: '.pace-name' })).toBeTruthy()
  })

  describe('the most recently processed match is the default (issues #174, #223)', () => {
    /** The matches are chosen in the Partidos tab (issue #476): open the tab, press «Ver» of the match, and the app goes to see it. */
    const pick = (label: RegExp) => {
      fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
      fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'demo' } })
      fireEvent.click(screen.getByRole('button', { name: label }))
    }
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
      render(<App initialTab="partido" engine={engine} {...props} />)
      await waitFor(() => expect(engine.loadRecording).toHaveBeenCalledWith('REC'))
      expect(engine.start).toHaveBeenLastCalledWith('REALPKG')
      expect(engine.loadReplay).not.toHaveBeenCalled()
      const title = await screen.findByLabelText(/partido de la demostración/i)
      expect(title.textContent).toContain('Recoletas Zamora – Mipelletymas B.F. Leon')
      expect(title.closest('section')?.querySelector('select')).toBeNull()                       // no selector here any more (#476)
      fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
      fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'demo' } })
      expect(within(screen.getByRole('region', { name: 'Partidos de demostración' })).getAllByRole('listitem').map(li => li.querySelector('span')?.textContent))
        .toEqual(['Recoletas Zamora – Mipelletymas B.F. Leon', 'Partido de ejemplo'])
    })

    describe('demos of the teams of interest (issue #441)', () => {
      const demo = (code: string, over = {}) => ({
        code, title: `Equipo ${code} – Rival ${code}`, date: '2026-10-18T18:30', home: { id: `h${code}`, name: `EQUIPO ${code}` }, away: { id: `a${code}`, name: `RIVAL ${code}` },
        recording: `${code}.recording.json`, package: `${code}.package.json`, ...over,
      })
      const MANY = [MANIFEST[0], demo('2536133', { competition: 'SEGUNDA FEB · Liga Regular A', teamId: '1008857' }), demo('2536851', { competition: 'TERCERA FEB · Liga Regular A-B', teamId: '1010490' })]
      const options = async () => {
        await screen.findByLabelText(/partido de la demostración/i)
        fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
        fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'demo' } })
        return within(screen.getByRole('region', { name: 'Partidos de demostración' })).getAllByRole('listitem').map(li => li.querySelector('span')?.textContent)
      }

      afterEach(() => localStorage.clear())

      it('the selector names the competition of the demos that have it, and the default one is still the one the app opens with', async () => {
        const engine = fakeEngine()
        render(<App initialTab="partido" engine={engine} {...props} loadManifest={() => Promise.resolve(MANY)} />)
        await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith('REALPKG'))
        expect((await screen.findByLabelText(/partido de la demostración/i)).textContent).toContain('Recoletas Zamora')
        expect(await options()).toEqual(['Recoletas Zamora – Mipelletymas B.F. Leon', 'SEGUNDA FEB · Liga Regular A — Equipo 2536133 – Rival 2536133',
          'TERCERA FEB · Liga Regular A-B — Equipo 2536851 – Rival 2536851', 'Partido de ejemplo'])
      })

      it('the demos of a team marked as de interés come first in the selector', async () => {
        localStorage.setItem('basketlab-live-favorites', JSON.stringify([{ teamId: '1010490', name: 'CAJA RURAL RDL' }]))
        render(<App initialTab="partido" engine={fakeEngine()} {...props} loadManifest={() => Promise.resolve(MANY)} />)
        expect((await options())[0]).toMatch(/TERCERA FEB/)
      })
    })

    it('opens at the first event of a recorded match, not at the minutes before it (issue #346)', async () => {
      const engine = fakeEngine({ loadRecording: vi.fn().mockResolvedValue({ duration: 7155, status: 'GRABACION', match: '2524470', frames: 353, start_at: 270 }) })
      render(<App initialTab="partido" engine={engine} {...props} />)
      await screen.findByLabelText(/partido de la demostración/i)
      expect(screen.getByText('4:30 / 119:15')).toBeTruthy()
    })

    describe('next event (issue #345)', () => {
      const EVENTS = [270, 285, 300, 1500]
      const withEvents = (events: number[] | undefined) =>
        fakeEngine({ loadRecording: vi.fn().mockResolvedValue({ duration: 7155, status: 'GRABACION', match: '2524470', frames: 353, start_at: 270, events }) })
      const next = () => fireEvent.click(screen.getByRole('button', { name: /siguiente evento/i }))

      it('jumps to the next moment with something new, without a question and without speeding up', async () => {
        const engine = withEvents(EVENTS)
        render(<App initialTab="partido" engine={engine} {...props} />)
        await screen.findByLabelText(/partido de la demostración/i)
        expect(screen.getByText('4:30 / 119:15')).toBeTruthy()
        next()
        expect(await screen.findByText('4:45 / 119:15')).toBeTruthy()
        next(); next()
        expect(await screen.findByText('25:00 / 119:15')).toBeTruthy()           // the long break is one step
        expect(screen.queryByRole('group', { name: /confirmar/i })).toBeNull()
        await waitFor(() => expect(engine.playRecording).toHaveBeenLastCalledWith(1500))
      })

      it('is disabled after the last event', async () => {
        render(<App initialTab="partido" engine={withEvents([270, 285])} {...props} />)
        await screen.findByLabelText(/partido de la demostración/i)
        next()
        await screen.findByText('4:45 / 119:15')
        expect((screen.getByRole('button', { name: /siguiente evento/i }) as HTMLButtonElement).disabled).toBe(true)
      })

      it('is not there for the sample game nor for a recording that does not list its events', async () => {
        render(<App initialTab="partido" engine={withEvents(undefined)} {...props} />)
        await screen.findByLabelText(/partido de la demostración/i)
        expect(screen.queryByRole('button', { name: /siguiente evento/i })).toBeNull()
      })
    })

    it('a recording that says nothing starts at 0:00, as before', async () => {
      render(<App initialTab="partido" engine={fakeEngine()} {...props} />)
      await screen.findByLabelText(/partido de la demostración/i)
      expect(screen.getByText('0:00 / 1:40')).toBeTruthy()
    })

    it('plays it second by second: waits for the match, shows the real 404 and then the alerts', async () => {
      const engine = fakeEngine()
      render(<App initialTab="partido" engine={engine} {...props} />)
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
      render(<App initialTab="partido" engine={engine} {...props} />)
      await screen.findByLabelText(/partido de la demostración/i)
      const sides = Array.from(document.querySelectorAll('.scoreboard .team .name')).map(n => n.textContent)
      expect(sides).toEqual(['EQUIPO RIVAL', 'EQUIPO PROPIO'])
    })

    it('without any recording it falls back to the sample game', async () => {
      const engine = fakeEngine()
      render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} loadMatch={loadMatch} />)
      await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledWith('GAME'))
      expect(engine.loadRecording).not.toHaveBeenCalled()
    })

    it('a manifest that cannot be read also falls back to the sample game', async () => {
      const engine = fakeEngine()
      render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} loadManifest={() => Promise.reject(new Error('404'))} loadMatch={loadMatch} />)
      await waitFor(() => expect(engine.loadReplay).toHaveBeenCalledWith('GAME'))
    })

    it('switches to the sample game and back to the recorded match', async () => {
      const engine = fakeEngine()
      render(<App initialTab="partido" engine={engine} {...props} />)
      await waitFor(() => expect(engine.loadRecording).toHaveBeenCalledTimes(1))
      pick(/ver partido de ejemplo/i)
      await waitFor(() => expect(engine.start).toHaveBeenLastCalledWith('PKG'))
      expect(engine.loadReplay).toHaveBeenLastCalledWith('GAME')
      await screen.findByLabelText(/partido de la demostración/i)
      pick(/ver recoletas zamora/i)
      await waitFor(() => expect(engine.loadRecording).toHaveBeenCalledTimes(2))
    })

    describe('the PDF report of a demo (issue #477)', () => {
      const pdf = () => ({ render: vi.fn(async () => new Uint8Array([1, 2, 3])), share: vi.fn(async () => undefined) })
      const REPORT = { match: { own: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' } } }
      const pkgText = JSON.stringify({ package: { team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' }, rule_config: { gender: 'F' } } })

      it('is built from the recording of the demo with the gender of its package and shared', async () => {
        const engine = fakeEngine({ report: vi.fn().mockResolvedValue(REPORT) })
        const p = pdf()
        render(<App initialTab="partido" engine={engine} {...props} loadMatch={() => Promise.resolve({ package: pkgText, recording: 'REC' })} pdf={p as never} />)
        await screen.findByLabelText(/partido de la demostración/i)
        fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
        fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'demo' } })
        fireEvent.click(screen.getByRole('button', { name: /informe pdf de recoletas zamora/i }))
        await waitFor(() => expect(p.share).toHaveBeenCalledTimes(1))
        expect(engine.report).toHaveBeenCalledWith('REC', [], '1', { gender: 'F' })
        expect((p.share.mock.calls[0] as unknown as string[])[2]).toContain('EQUIPO PROPIO – EQUIPO RIVAL')
      })

      it('the sample game has its report too', async () => {
        const engine = fakeEngine({ report: vi.fn().mockResolvedValue(REPORT) })
        const p = pdf()
        render(<App initialTab="partido" engine={engine} {...props} loadDemo={() => Promise.resolve({ package: pkgText, game: 'GAME' })} pdf={p as never} />)
        await screen.findByLabelText(/partido de la demostración/i)
        fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
        fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'demo' } })
        fireEvent.click(screen.getByRole('button', { name: /informe pdf de partido de ejemplo/i }))
        await waitFor(() => expect(p.share).toHaveBeenCalledTimes(1))
        expect(engine.report).toHaveBeenCalledWith('GAME', [], '1', { gender: 'F' })
      })

      it('a failure is said where the button is, and the buttons come back', async () => {
        const engine = fakeEngine({ report: vi.fn().mockRejectedValue(new Error('motor')) })
        render(<App initialTab="partido" engine={engine} {...props} loadMatch={() => Promise.resolve({ package: pkgText, recording: 'REC' })} pdf={pdf() as never} />)
        await screen.findByLabelText(/partido de la demostración/i)
        fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
        fireEvent.change(screen.getByLabelText('Tipo de partido'), { target: { value: 'demo' } })
        fireEvent.click(screen.getByRole('button', { name: /informe pdf de recoletas zamora/i }))
        expect(await screen.findByText(/no se pudo generar el informe: motor/i)).toBeTruthy()
        expect((screen.getByRole('button', { name: /informe pdf de recoletas zamora/i }) as HTMLButtonElement).disabled).toBe(false)
      })
    })

    it('the demo notice of the Partido tab is gone: the matches are in the Partidos tab (issue #476)', async () => {
      render(<App initialTab="partido" engine={fakeEngine()} {...props} />)
      await screen.findByLabelText(/partido de la demostración/i)
      expect(screen.queryByText(/estás viendo un partido de demostración/i)).toBeNull()
    })

    it('says so and shows the sample game when the recording cannot be loaded', async () => {
      const engine = fakeEngine()
      render(<App initialTab="partido" engine={engine} loadDemo={loadDemo} loadManifest={loadManifest} loadMatch={() => Promise.reject(new Error('sin red'))} />)
      expect(await screen.findByText(/no se pudo cargar el partido/i)).toBeTruthy()
      expect(engine.loadReplay).toHaveBeenCalledWith('GAME')
    })
  })
})
