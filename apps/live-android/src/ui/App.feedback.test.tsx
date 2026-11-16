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
  update: vi.fn(), loadRecording: vi.fn(), playRecording: vi.fn(), report: vi.fn(), beginRecording: vi.fn(), recordGap: vi.fn(), updateStreaming: vi.fn(), updateFbcylFinal: vi.fn(), lastDocument: vi.fn(), recording: vi.fn(), setMode: vi.fn(), dispose: vi.fn(),
})
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })
const KEY = 'basketlab-live-feedback:demo:sample'

async function playUntilTheAlert() {
  render(<App initialTab="partido" engine={engine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} />)
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

describe('App feedback (issue #235) and dismissal (issue #933)', () => {
  it('every shown alert is registered on the device, with the game second and the real time', async () => {
    await playUntilTheAlert()
    const saved = JSON.parse(localStorage.getItem(KEY)!)
    expect(saved).toHaveLength(1)
    expect(saved[0]).toMatchObject({ key: 'foul:9:3', id: 'foul_trouble', severity: 'critical', verdict: null })
    expect(saved[0].elapsed).toBeGreaterThanOrEqual(5)
    expect(Number.isNaN(Date.parse(saved[0].shown_at))).toBe(false)
  })

  it('the staff no longer sees the answers nor the feedback panel', async () => {
    await playUntilTheAlert()
    for (const old of ['Seguida', 'Descartada', 'Ya hecho', 'Borrar']) expect(screen.queryByRole('button', { name: old })).toBeNull()
    expect(screen.queryByText(/alertas valoradas/i)).toBeNull()
  })

  it('dismissing an alert hides it, keeps it in the list of dismissed and saves it on the device', async () => {
    await playUntilTheAlert()
    fireEvent.click(screen.getByRole('button', { name: 'Descartar aviso' }))
    expect(screen.queryByText(/4 faltas personales/, { selector: '.alert-message' })).toBeNull()
    expect(screen.getByText(/Descartados · 1/)).toBeTruthy()
    expect(JSON.parse(localStorage.getItem(KEY)!)[0].verdict).toBe('descartada')
    fireEvent.click(screen.getByRole('button', { name: 'Recuperar aviso' }))
    expect(screen.getByText(/4 faltas personales/, { selector: '.alert-message' })).toBeTruthy()
    expect(JSON.parse(localStorage.getItem(KEY)!)[0].verdict).toBeNull()
  })

  it('a dismissed alert stays dismissed after the app is opened again and the match replayed', async () => {
    await playUntilTheAlert()
    fireEvent.click(screen.getByRole('button', { name: 'Descartar aviso' }))
    document.body.innerHTML = ''
    await playUntilTheAlert()
    expect(screen.getByText(/Descartados · 1/)).toBeTruthy()
  })
})
