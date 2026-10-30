import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

// Issue #194 (U5c): Tiros on the base components. The three choices of a few are named radio groups, the player chip has its icon button, one h1.
describe('ShotChartPage on the base components (issue #194)', () => {
  beforeEach(() => {
    Object.values(api).forEach(f => f.mockReset())
    api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo FBCYL' }])
    api.getShotZones.mockResolvedValue([])
    api.getShotRaw.mockResolvedValue([])
    api.getPlayerStats.mockResolvedValue([])
    api.getPlayerQuartiles.mockResolvedValue({})
  })

  it('has one h1 with the competition as its subtitle', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Gráficos de Tiro' })).toBeInTheDocument()
    expect(screen.getByText('FBCYL 1A')).toBeInTheDocument()
  })

  it('what to see, how to draw it and which shots are named radio groups; the result filter only where it applies', async () => {
    renderPage()
    const see = screen.getByRole('radiogroup', { name: 'Ver por' })
    expect(within(see).getAllByRole('radio').map(r => r.textContent)).toEqual(['Equipo', 'Jugador'])
    expect(within(see).getByRole('radio', { name: 'Equipo' })).toHaveAttribute('aria-checked', 'true')
    const viz = screen.getByRole('radiogroup', { name: 'Visualización' })
    expect(within(viz).getAllByRole('radio').map(r => r.textContent)).toEqual(['Zonas', 'Scatter', 'Calor'])
    expect(screen.queryByRole('radiogroup', { name: 'Resultado del tiro' })).toBeNull()      // zones: no filter by result
    fireEvent.click(within(viz).getByRole('radio', { name: 'Scatter' }))
    const result = screen.getByRole('radiogroup', { name: 'Resultado del tiro' })
    expect(within(result).getAllByRole('radio').map(r => r.textContent)).toEqual(['Todos', 'Aciertos', 'Fallos'])
    fireEvent.click(within(result).getByRole('radio', { name: 'Fallos' }))
    expect(within(screen.getByRole('radiogroup', { name: 'Resultado del tiro' })).getByRole('radio', { name: 'Fallos' })).toHaveAttribute('aria-checked', 'true')
  })
})
