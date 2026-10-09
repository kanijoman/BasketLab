import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getLiveTeamNames: vi.fn() }))
const pkg = vi.hoisted(() => ({
  startLivePackage: vi.fn(),
  getLivePackageProgress: vi.fn(),
  downloadLivePackage: vi.fn(),
  getLiveMatches: vi.fn(),
}))
const collectionState = vi.hoisted(() => ({ value: { name: 'FEB_X', label: 'FEB X', isFbcyl: false } }))
vi.mock('@/api/client', () => api)
vi.mock('@/api/livePackage', () => pkg)
vi.mock('@/context/CollectionContext', () => ({ useCollection: () => ({ collection: collectionState.value }) }))

import LivePrepPage from './LivePrepPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><LivePrepPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

async function fill(pass = 'clave-segura-1', repeat?: string) {
  await screen.findAllByRole('option', { name: 'Equipo B' })
  fireEvent.change(screen.getByLabelText(/equipo propio/i), { target: { value: '1' } })
  fireEvent.change(screen.getByLabelText(/rival/i), { target: { value: '2' } })
  fireEvent.change(screen.getByLabelText(/^contraseña$/i), { target: { value: pass } })
  fireEvent.change(screen.getByLabelText(/repetir contraseña/i), { target: { value: repeat ?? pass } })
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  Object.values({ ...api, ...pkg }).forEach(f => f.mockReset())
  collectionState.value = { name: 'FEB_X', label: 'FEB X', isFbcyl: false }
  api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo A' }, { id: '2', name: 'Equipo B' }])
  pkg.startLivePackage.mockResolvedValue({ job_id: 'j1' })
  pkg.getLivePackageProgress
    .mockResolvedValueOnce({ status: 'running', current: 2, total: 5, team: 'Equipo A', rival: 'Equipo B', error: null })
    .mockResolvedValue({ status: 'done', current: 5, total: 5, team: 'Equipo A', rival: 'Equipo B', error: null })
  pkg.downloadLivePackage.mockResolvedValue(new Blob(['{}']))
  pkg.getLiveMatches.mockResolvedValue({ matches: [], calendar_url: 'u', warning: null })
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() })
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('LivePrepPage', () => {
  it('lists the teams of the competition for both selectors', async () => {
    renderPage()
    expect(await screen.findAllByRole('option', { name: 'Equipo A' })).toHaveLength(2)
  })

  it('does not allow generating without teams or with a short or mismatching password', async () => {
    renderPage()
    await fill('corta')
    expect(screen.getByRole('button', { name: /generar paquete/i })).toBeDisabled()
    await fill('clave-segura-1', 'otra-distinta-1')
    expect(screen.getByRole('button', { name: /generar paquete/i })).toBeDisabled()
    expect(screen.getByText(/no coinciden/i)).toBeTruthy()
  })

  it('rejects the same team as own and rival', async () => {
    renderPage()
    await fill()
    fireEvent.change(screen.getByLabelText(/rival/i), { target: { value: '1' } })
    expect(screen.getByRole('button', { name: /generar paquete/i })).toBeDisabled()
  })

  it('generates, shows progress and downloads the file', async () => {
    renderPage()
    await fill()
    fireEvent.click(screen.getByRole('button', { name: /generar paquete/i }))
    await waitFor(() => expect(pkg.startLivePackage).toHaveBeenCalledWith(
      { collection: 'FEB_X', team_id: '1', rival_id: '2', passphrase: 'clave-segura-1' }))
    expect(await screen.findByText(/2 de 5 partidos/i)).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(2500) })
    await waitFor(() => expect(pkg.downloadLivePackage).toHaveBeenCalledWith('j1'))
    expect(await screen.findByText(/paquete descargado/i)).toBeTruthy()
    expect(screen.getByText(/guarda la contraseña/i)).toBeTruthy()
  })

  it('reports a generation failure', async () => {
    pkg.getLivePackageProgress.mockReset().mockResolvedValue({ status: 'error', current: 1, total: 5, team: '', rival: '', error: 'db down' })
    renderPage()
    await fill()
    fireEvent.click(screen.getByRole('button', { name: /generar paquete/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(2500) })
    expect(await screen.findByText(/db down/)).toBeTruthy()
    expect(pkg.downloadLivePackage).not.toHaveBeenCalled()
  })

  it('shows the server message when another package is already being built', async () => {
    pkg.startLivePackage.mockRejectedValue(new Error('Ya hay un paquete en preparación'))
    renderPage()
    await fill()
    fireEvent.click(screen.getByRole('button', { name: /generar paquete/i }))
    expect(await screen.findByText(/Ya hay un paquete en preparación/)).toBeTruthy()
  })

  it('explains that FBCYL competitions are not supported yet', async () => {
    collectionState.value = { name: 'FBCYL_X', label: 'FBCYL X', isFbcyl: true }
    renderPage()
    expect(await screen.findByText(/solo.*FEB/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /generar paquete/i })).toBeNull()
  })

  describe('match suggestions from the FEB calendar', () => {
    const matches = [
      { code: '2524465', kind: 'scheduled', status: 'scheduled', start: '2026-10-10T19:00', round: 2, is_home: true,
        opponent: { id: '2', name: 'Equipo B' }, home: { id: '1', name: 'Equipo A' }, away: { id: '2', name: 'Equipo B' } },
      { code: '2524475', kind: 'scheduled', status: 'live', start: null, round: 3, is_home: false,
        opponent: { id: '3', name: 'Equipo C' }, home: { id: '3', name: 'Equipo C' }, away: { id: '1', name: 'Equipo A' } },
    ]

    it('lists the next matches of the chosen team, live ones flagged', async () => {
      pkg.getLiveMatches.mockResolvedValue({ matches, calendar_url: 'u', warning: null })
      renderPage()
      await fill()
      expect(await screen.findByRole('radio', { name: /Equipo B/ })).toBeTruthy()
      expect(pkg.getLiveMatches).toHaveBeenCalledWith('FEB_X', '1', 5)
      expect(screen.getByText(/en directo/i)).toBeTruthy()
    })

    it('choosing a match selects the rival and sends the match code', async () => {
      pkg.getLiveMatches.mockResolvedValue({ matches, calendar_url: 'u', warning: null })
      renderPage()
      await fill()
      fireEvent.click(await screen.findByRole('radio', { name: /Equipo B/ }))
      expect((screen.getByLabelText(/rival/i) as HTMLSelectElement).value).toBe('2')
      fireEvent.click(screen.getByRole('button', { name: /generar paquete/i }))
      await waitFor(() => expect(pkg.startLivePackage).toHaveBeenCalledWith(
        { collection: 'FEB_X', team_id: '1', rival_id: '2', passphrase: 'clave-segura-1', match_code: '2524465' }))
    })

    it('changing the rival by hand drops the match selection', async () => {
      api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo A' }, { id: '2', name: 'Equipo B' }, { id: '3', name: 'Equipo C' }])
      pkg.getLiveMatches.mockResolvedValue({ matches, calendar_url: 'u', warning: null })
      renderPage()
      await fill()
      fireEvent.click(await screen.findByRole('radio', { name: /Equipo B/ }))
      fireEvent.change(screen.getByLabelText(/rival/i), { target: { value: '3' } })
      expect((screen.getByRole('radio', { name: /Equipo B/ }) as HTMLInputElement).checked).toBe(false)
      fireEvent.click(screen.getByRole('button', { name: /generar paquete/i }))
      await waitFor(() => expect(pkg.startLivePackage.mock.calls[0][0].match_code).toBeUndefined())
    })

    it('shows the calendar warning and still allows choosing the rival by hand', async () => {
      pkg.getLiveMatches.mockResolvedValue({ matches: [], calendar_url: null, warning: 'No se pudo leer el calendario de FEB' })
      renderPage()
      await fill()
      expect(await screen.findByText(/No se pudo leer el calendario/)).toBeTruthy()
      expect(screen.getByRole('button', { name: /generar paquete/i })).not.toBeDisabled()
    })

    it('does not break when the match request fails', async () => {
      pkg.getLiveMatches.mockRejectedValue(new Error('boom'))
      renderPage()
      await fill()
      await waitFor(() => expect(pkg.getLiveMatches).toHaveBeenCalled())
      expect(screen.getByRole('button', { name: /generar paquete/i })).not.toBeDisabled()
    })
  })
})
