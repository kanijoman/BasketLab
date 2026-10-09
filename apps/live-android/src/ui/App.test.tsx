import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'

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

const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })
const replayCalls = (e: EngineApi) => (e.replay as ReturnType<typeof vi.fn>).mock.calls

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }))
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
})
