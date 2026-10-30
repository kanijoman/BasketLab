import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getTeamStats: vi.fn(), streamRotacionesAnalysis: vi.fn() }))
vi.mock('@/api/client', async () => ({ ...(await vi.importActual<object>('@/api/client')), ...api }))
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import RotacionesPage from './RotacionesPage'

// Issue #194 (U5c): Rotaciones on the base components — one h1 with the competition as its subtitle; the team a labelled select that picks the first
// by itself; the analysis button says it is working while the stream runs, and the team is the one chosen.
function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><RotacionesPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getTeamStats.mockReset().mockResolvedValue({ team_stats: [{ team_name: 'Bravo', team_id: 2 }, { team_name: 'Alfa', team_id: 1 }], opponent_stats: [] })
  api.streamRotacionesAnalysis.mockReset().mockReturnValue(new Promise(() => undefined))
})

describe('RotacionesPage on the base components (issue #194)', () => {
  it('has one h1 with the competition as its subtitle', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Análisis de Rotaciones' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the analysis button says it is working while it runs, for the team chosen', async () => {
    renderPage()
    await screen.findByRole('option', { name: 'Alfa' })
    await waitFor(() => expect(screen.getByLabelText('Equipo')).toHaveValue('1'))      // the first team, sorted by name
    fireEvent.change(screen.getByLabelText('Equipo'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    const working = await screen.findByRole('button', { name: /Analizando/ })
    expect(working).toHaveAttribute('aria-busy', 'true')
    expect(working).toBeDisabled()
    expect(api.streamRotacionesAnalysis).toHaveBeenCalledWith('LF_CHALLENGE', '2', 'Bravo', expect.any(Function))
  })
})
