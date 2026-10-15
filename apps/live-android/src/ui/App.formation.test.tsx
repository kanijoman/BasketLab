import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { EngineApi } from '../engine/client'
import type { EngineOutput } from '../engine/types'

const META = {
  package_id: 'p', schema_version: 1, created_at: '', collection: 'c', season: '2025',
  team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
}
const out = (elapsed: number, formation: object | undefined): EngineOutput => ({
  snapshot: { period: 3, remaining: 600 - elapsed, elapsed, score: { '1': 1, '2': 0 } } as never,
  alerts: [],
  analysis: { formation } as never,
})
const engine = (formation: object | undefined): EngineApi => ({
  start: vi.fn().mockResolvedValue(META),
  loadReplay: vi.fn().mockResolvedValue({ duration: 100, status: 'FINISHED' }),
  replay: vi.fn(async (e: number) => out(e, formation)),
  update: vi.fn(), loadRecording: vi.fn(), playRecording: vi.fn(), setMode: vi.fn(), dispose: vi.fn(),
})
const loadDemo = () => Promise.resolve({ package: 'PKG', game: 'GAME' })

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

async function play(formation: object | undefined) {
  render(<App engine={engine(formation)} loadDemo={loadDemo} loadManifest={() => Promise.resolve([])} />)
  await screen.findByText('EQUIPO PROPIO')
  fireEvent.click(screen.getByRole('button', { name: /reproducir/i }))
  await act(async () => { await vi.advanceTimersByTimeAsync(3000) })
}

describe('App formation status (issues #272 and #322)', () => {
  it('says nothing under the scoreboard while both lineups are watched: an illegal one is a critical alert, not a card', async () => {
    await play({ min: 2, known: true, on_court: 1, unknown: 0, players: 5, rival: { known: true, on_court: 0, unknown: 0, players: 5 } })
    expect(screen.queryByText(/formación/i)).toBeNull()
  })

  it('warns that a team is not being watched when the package has no roster of it', async () => {
    await play({ min: 2, known: false, on_court: null, unknown: 0, players: 5, rival: { known: true, on_court: 3, unknown: 0, players: 5 } })
    await waitFor(() => expect(screen.getByText(/no se vigila la alineación de formación de EQUIPO PROPIO/i)).toBeTruthy())
  })

  it('also for the rival', async () => {
    await play({ min: 2, known: true, on_court: 3, unknown: 0, players: 5, rival: { known: false, on_court: null, unknown: 0, players: 0 } })
    await waitFor(() => expect(screen.getByText(/no se vigila la alineación de formación de EQUIPO RIVAL/i)).toBeTruthy())
  })

  it('shows nothing about formación without the data', async () => {
    await play(undefined)
    expect(screen.queryByText(/formación/i)).toBeNull()
  })
})
