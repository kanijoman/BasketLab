import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getPlayerStats: vi.fn(), getTeamStats: vi.fn(), getInOutAnalysis: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import InOutPage from './InOutPage'

// Issue #194 (U5c): IN/OUT on the base components — one h1 with the competition as its subtitle and the two views as tabs (with the keyboard).
function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><InOutPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getPlayerStats.mockReset().mockResolvedValue([])
  api.getTeamStats.mockReset().mockResolvedValue([])
  api.getInOutAnalysis.mockReset().mockResolvedValue(null)
})

// Issue #711: the table lists an FBCYL player by the actorId of one game; the analysis looks for his uuid, so the page asks for that.
describe('InOutPage: an FBCYL player (issue #711)', () => {
  it('asks for the analysis with his uuid', async () => {
    const uuid = '593291b9-ff22-4545-b7b3-88159242a0d8'
    api.getPlayerStats.mockResolvedValue([{ player_id: '872552', player_uuid: uuid, player_name: 'F. NUEVO', team_name: 'Alfa', team_id: '1', games_played: 3 }])
    renderPage()
    await screen.findByRole('option', { name: /F\. NUEVO/ })
    fireEvent.change(screen.getByLabelText('Jugador'), { target: { value: uuid } })
    await waitFor(() => expect(api.getInOutAnalysis).toHaveBeenCalledWith('LF_CHALLENGE', uuid))
  })
})

describe('InOutPage on the base components (issue #194)', () => {
  it('has one h1 with the competition as its subtitle', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Análisis IN/OUT' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the two views are tabs: IN/OUT open, the arrow of the keyboard opens IN vs IN', () => {
    renderPage()
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['IN/OUT', 'IN vs IN'])
    expect(screen.getByRole('tab', { name: 'IN/OUT' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'IN/OUT' }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'IN vs IN' })).toHaveAttribute('aria-selected', 'true')
  })
})
