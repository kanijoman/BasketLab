import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}
const ALERT = {
  key: 'foul:9:3', id: 'foul_trouble', severity: 'critical' as const, category: 'faltas',
  message: 'J. PÉREZ: 4 faltas personales. Gestionar sus minutos.', evidence: {}, rearm_s: null, proposal: [],
}
const out = (elapsed: number): EngineOutput => ({
  snapshot: { period: 1, remaining: 600 - elapsed, elapsed, score: { '1': 0, '2': 0 } } as never,
  alerts: elapsed >= 5 ? [ALERT] : [],
  analysis: {},
})
const engine = (): EngineApi => ({
  start: vi.fn().mockResolvedValue(META),
  loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
  replay: vi.fn(async (e: number) => out(e)),
  update: vi.fn(), loadRecording: vi.fn(), playRecording: vi.fn(), setMode: vi.fn(), dispose: vi.fn(),
})
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })
const KEY = 'basketlab-live-feedback:demo:sample'

async function playUntilTheAlert() {
  render(<App engine={engine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} />)
  await screen.findByText('EQUIPO PROPIO')
  fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
  await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
  await waitFor(() => expect(screen.getByText(/4 faltas personales/)).toBeTruthy())
}

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

describe('App feedback (issue #235)', () => {
  it('every shown alert is registered on the device, with the game second and the real time', async () => {
    await playUntilTheAlert()
    const saved = JSON.parse(localStorage.getItem(KEY)!)
    expect(saved).toHaveLength(1)
    expect(saved[0]).toMatchObject({ key: 'foul:9:3', id: 'foul_trouble', severity: 'critical', verdict: null })
    expect(saved[0].elapsed).toBeGreaterThanOrEqual(5)
    expect(Number.isNaN(Date.parse(saved[0].shown_at))).toBe(false)
  })

  it('answering an alert marks the button, saves the verdict and updates the count', async () => {
    await playUntilTheAlert()
    expect(screen.getByText(/0 de 1 alertas valoradas/i)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Seguida' }))
    expect(screen.getByRole('button', { name: 'Seguida' }).getAttribute('aria-pressed')).toBe('true')
    expect(JSON.parse(localStorage.getItem(KEY)!)[0].verdict).toBe('seguida')
    expect(screen.getByText(/1 de 1 alertas valoradas/i)).toBeTruthy()
  })

  it('the answer is still there after the app is opened again and the match replayed', async () => {
    await playUntilTheAlert()
    fireEvent.click(screen.getByRole('button', { name: 'Ya hecho' }))
    document.body.innerHTML = ''
    await playUntilTheAlert()
    expect(screen.getByRole('button', { name: 'Ya hecho' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('clearing removes the history of the match', async () => {
    await playUntilTheAlert()
    fireEvent.click(screen.getByRole('button', { name: 'Seguida' }))
    fireEvent.click(screen.getByRole('button', { name: 'Borrar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar borrado' }))
    expect(screen.getByRole('button', { name: 'Seguida' }).getAttribute('aria-pressed')).toBe('false')
    expect(JSON.parse(localStorage.getItem(KEY) ?? '[]')).toEqual([])
  })

  // Issue #314: "0 de 53" with 40 alerts on the screen — the history of earlier runs of the same match was counted
  it('the count is about the alerts of this run, not the history of earlier runs', async () => {
    const stale = ['a', 'b', 'c'].map(key => ({ key, id: 'x', severity: 'info', category: 'rival', message: 'm', elapsed: 900, shown_at: '2026-10-14T10:00:00Z', verdict: null }))
    localStorage.setItem(KEY, JSON.stringify(stale))
    await playUntilTheAlert()
    expect(screen.getByText(/0 de 1 alertas valoradas/i)).toBeTruthy()
    expect(screen.queryByText(/de 4 alertas/i)).toBeNull()
  })

  it('after a restart the count starts again from the alerts that come back, and the answers stay', async () => {
    await playUntilTheAlert()
    fireEvent.click(screen.getByRole('button', { name: 'Seguida' }))
    fireEvent.click(screen.getByRole('button', { name: 'Reiniciar' }))
    fireEvent.click(screen.getByRole('button', { name: /sí, reiniciar/i }))
    await waitFor(() => expect(screen.queryByText(/alertas valoradas/i)).toBeNull())      // nothing shown yet: no panel
    fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    await waitFor(() => expect(screen.getByText(/1 de 1 alertas valoradas/i)).toBeTruthy())
  })
})
