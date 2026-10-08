import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getLiveTeamNames: vi.fn(),
  getShotZones: vi.fn(),
  getShotRaw: vi.fn(),
  getPlayerStats: vi.fn(),
  getPlayerQuartiles: vi.fn(),
}))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'FBCYL_1A_2026', label: 'FBCYL 1A', isFbcyl: true } }),
}))

import ShotChartPage from './ShotChartPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><ShotChartPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ShotChartPage with a FBCYL collection (#150)', () => {
  beforeEach(() => {
    Object.values(api).forEach(f => f.mockReset())
    api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo FBCYL' }])
    api.getShotZones.mockResolvedValue([])
    api.getShotRaw.mockResolvedValue([])
    api.getPlayerStats.mockResolvedValue([])
    api.getPlayerQuartiles.mockResolvedValue({})
  })

  it('is available (no "No disponible para FBCYL" notice) and lists the teams', async () => {
    renderPage()
    await waitFor(() => expect(api.getLiveTeamNames).toHaveBeenCalledWith('FBCYL_1A_2026'))
    expect(screen.queryByText(/No disponible para FBCYL/i)).toBeNull()
    expect(await screen.findByText('Equipo FBCYL')).toBeTruthy()
  })
})
