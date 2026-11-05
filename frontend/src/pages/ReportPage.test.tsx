import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getLiveTeamNames: vi.fn() }))
const weekly = vi.hoisted(() => ({ downloadWeeklyReport: vi.fn() }))
const scouting = vi.hoisted(() => ({ downloadIndividualScoutingDocx: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/api/individualScouting', () => scouting)
vi.mock('@/api/weeklyReport', () => weekly)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import ReportPage from './ReportPage'

// Issue #193 (U5b): Informes on the base components — one h1, the teams labelled selects, the downloads buttons that say they are working (aria-busy)
// and stay off until what they need is chosen. What each download asks the API for is the page's own and does not change.
const TEAMS = [{ id: '1', name: 'Alfa' }, { id: '2', name: 'Bravo' }]
const realUrl = URL

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><ReportPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  Object.values(api).forEach(f => f.mockReset())
  api.getLiveTeamNames.mockResolvedValue(TEAMS)
  vi.stubGlobal('URL', { ...realUrl, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() })
})
afterEach(() => vi.stubGlobal('URL', realUrl))

describe('ReportPage on the base components (issue #193)', () => {
  it('has one h1 with the competition as its subtitle and the two cards', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Informes' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
    expect(screen.getByText('Informe Semanal')).toBeInTheDocument()
    expect(screen.getByText('Scouting Individual')).toBeInTheDocument()
  })

  it('the weekly ZIP waits for two different teams and says so when they are the same', async () => {
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    const zip = screen.getByRole('button', { name: 'Descargar ZIP' })
    expect(zip).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Equipo propio (A)'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Equipo rival (B)'), { target: { value: '1' } })
    expect(screen.getByText(/deben ser diferentes/)).toBeInTheDocument()
    expect(zip).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Equipo rival (B)'), { target: { value: '2' } })
    expect(screen.queryByText(/deben ser diferentes/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Descargar ZIP' })).toBeEnabled()
  })

  it('the weekly report shows its progress as it goes, the button says it is working until it is done, and the zip is saved', async () => {
    let finish: (blob: Blob) => void = () => {}
    weekly.downloadWeeklyReport.mockImplementation((_c: string, _a: string, _b: string, onProgress: (p: unknown) => void) => {
      onProgress({ status: 'running', step: 2, total: 5, message: 'Último partido — Alfa', error: null })
      return new Promise<Blob>(resolve => { finish = resolve })
    })
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    fireEvent.change(screen.getByLabelText('Equipo propio (A)'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Equipo rival (B)'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Descargar ZIP' }))
    const working = await screen.findByRole('button', { name: /Generando informe/ })
    expect(working).toHaveAttribute('aria-busy', 'true')
    expect(working).toBeDisabled()
    expect(await screen.findByText(/Último partido — Alfa \(2\/5\)/)).toBeInTheDocument()
    expect(weekly.downloadWeeklyReport).toHaveBeenCalledWith('LF_CHALLENGE', '1', '2', expect.any(Function))
    finish(new Blob(['zip']))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar ZIP' })).toBeEnabled())
  })

  it('the weekly report says why it failed instead of only logging it, and a new try clears it', async () => {
    weekly.downloadWeeklyReport.mockRejectedValueOnce(new Error('Uno de los equipos no está en esta competición.'))
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    fireEvent.change(screen.getByLabelText('Equipo propio (A)'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Equipo rival (B)'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Descargar ZIP' }))
    expect(await screen.findByText('Uno de los equipos no está en esta competición.')).toBeInTheDocument()
    weekly.downloadWeeklyReport.mockResolvedValueOnce(new Blob(['zip']))
    fireEvent.click(screen.getByRole('button', { name: 'Descargar ZIP' }))
    await waitFor(() => expect(screen.queryByText('Uno de los equipos no está en esta competición.')).toBeNull())
  })

  it('the individual scouting DOCX shows its progress as it goes (#215): the charts of each player, then the document', async () => {
    let finish: (blob: Blob) => void = () => {}
    scouting.downloadIndividualScoutingDocx.mockImplementation((_c: string, _t: string, onProgress: (p: unknown) => void) => {
      onProgress({ stage: 'charts', current: 2, total: 5 })
      return new Promise<Blob>(resolve => { finish = resolve })
    })
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    fireEvent.change(screen.getByLabelText('Equipo a analizar'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Descargar DOCX' }))
    expect(await screen.findByRole('progressbar', { name: 'Gráficos de los jugadores (2/5)' })).toBeInTheDocument()
    finish(new Blob(['docx']))
    await waitFor(() => expect(screen.queryByRole('progressbar')).toBeNull())
  })

  it('the individual scouting DOCX waits for a team, downloads it and says why when it fails', async () => {
    scouting.downloadIndividualScoutingDocx.mockRejectedValueOnce(new Error('FEB no responde'))
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    expect(screen.getByRole('button', { name: 'Descargar DOCX' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Equipo a analizar'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Descargar DOCX' }))
    expect(await screen.findByText('FEB no responde')).toBeInTheDocument()
    expect(scouting.downloadIndividualScoutingDocx).toHaveBeenCalledWith('LF_CHALLENGE', '2', expect.any(Function))
    scouting.downloadIndividualScoutingDocx.mockResolvedValueOnce(new Blob(['docx']))
    fireEvent.click(screen.getByRole('button', { name: 'Descargar DOCX' }))
    await waitFor(() => expect(screen.queryByText('FEB no responde')).toBeNull())
  })
})
