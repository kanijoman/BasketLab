import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getLiveTeamNames: vi.fn(), postWeeklyReport: vi.fn(), getWeeklyReportProgress: vi.fn(), downloadWeeklyReport: vi.fn(), downloadIndividualScoutingDocx: vi.fn(),
}))
vi.mock('@/api/client', () => api)
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

  it('the weekly report asks for the job, shows its progress and the button says it is working until it is done', async () => {
    api.postWeeklyReport.mockResolvedValue({ job_id: 'j1' })
    api.getWeeklyReportProgress.mockResolvedValue({ status: 'done', step: 5, total: 5, message: 'Listo', error: null })
    api.downloadWeeklyReport.mockResolvedValue(new Blob(['zip']))
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    fireEvent.change(screen.getByLabelText('Equipo propio (A)'), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText('Equipo rival (B)'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Descargar ZIP' }))
    const working = await screen.findByRole('button', { name: /Generando informe/ })
    expect(working).toHaveAttribute('aria-busy', 'true')
    expect(working).toBeDisabled()
    expect(api.postWeeklyReport).toHaveBeenCalledWith('LF_CHALLENGE', '1', '2')
    await waitFor(() => expect(api.downloadWeeklyReport).toHaveBeenCalledWith('j1'), { timeout: 4000 })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar ZIP' })).toBeEnabled(), { timeout: 4000 })
  })

  it('the individual scouting DOCX waits for a team, downloads it and says why when it fails', async () => {
    api.downloadIndividualScoutingDocx.mockRejectedValueOnce(new Error('FEB no responde'))
    renderPage()
    await screen.findAllByRole('option', { name: 'Alfa' })
    expect(screen.getByRole('button', { name: 'Descargar DOCX' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Equipo a analizar'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Descargar DOCX' }))
    expect(await screen.findByText('FEB no responde')).toBeInTheDocument()
    expect(api.downloadIndividualScoutingDocx).toHaveBeenCalledWith('LF_CHALLENGE', '2')
    api.downloadIndividualScoutingDocx.mockResolvedValueOnce(new Blob(['docx']))
    fireEvent.click(screen.getByRole('button', { name: 'Descargar DOCX' }))
    await waitFor(() => expect(screen.queryByText('FEB no responde')).toBeNull())
  })
})
