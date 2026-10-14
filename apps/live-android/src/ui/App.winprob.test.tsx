import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}
const out = (elapsed: number): EngineOutput => ({
  snapshot: { period: 2, remaining: 600 - elapsed, elapsed, score: { '1': 30, '2': 26 } } as never,
  alerts: [],
  analysis: {
    win_prob: { p: 0.71, projected_margin: 6.2, sd: 8, poss_remaining: 35, mu_per_100: 2, reliable: true },
    win_levers: [{ id: 'tov', gain: 0.04, gain_pts: 1.2, proposal: [] }],
  },
})
const engine = (): EngineApi => ({
  start: vi.fn().mockResolvedValue(META),
  loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
  replay: vi.fn(async (e: number) => out(e)),
  update: vi.fn(), loadRecording: vi.fn(), playRecording: vi.fn(), dispose: vi.fn(),
})
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

async function play() {
  render(<App engine={engine()} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} />)
  await screen.findByText('EQUIPO PROPIO')
  fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
  await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
}

describe('App win probability (issue #257, experimental)', () => {
  it('shows the card in the match tab', async () => {
    await play()
    await waitFor(() => expect(screen.getByRole('region', { name: 'Probabilidad de victoria' })).toBeTruthy())
    expect(screen.getByText('71 %')).toBeTruthy()
    expect(screen.getByText(/pérdidas/i)).toBeTruthy()
  })

  it('the staff can switch it off in Acerca de, and it stays off', async () => {
    await play()
    await waitFor(() => expect(screen.getByText('71 %')).toBeTruthy())
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    const toggle = screen.getByRole('checkbox', { name: /probabilidad de victoria/i }) as HTMLInputElement
    expect(toggle.checked).toBe(true)
    fireEvent.click(toggle)
    fireEvent.click(screen.getByRole('tab', { name: 'Partido' }))
    expect(screen.queryByRole('region', { name: 'Probabilidad de victoria' })).toBeNull()
  })
})
