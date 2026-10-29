import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getSiblingCollections: vi.fn(), getMultiTeamStats: vi.fn(), getMultiPlayerStats: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico', label: 'Primera FEB', isFbcyl: false } }),
}))

import MultiPhaseStatsPage from './MultiPhaseStatsPage'

// Issue #192 (U5a): Multifase on the components of components/ui. The phases to combine are toggle buttons that say whether they are in, the parts are
// tabs (entity and kind of stat), and the page has one h1. What it combines, and when it asks the API for it, is unchanged.
const SIBLINGS = ['PRIMERA_FEB_2026_2027_Liga_Regular_Unico', 'PRIMERA_FEB_2026_2027_Play-offs']
const team = (name: string) => ({ team_name: name, team_id: name, total_games: 10, points_per_game: 75, points_against_per_game: 70 })

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><MultiPhaseStatsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getSiblingCollections.mockReset().mockResolvedValue(SIBLINGS)
  api.getMultiTeamStats.mockReset().mockResolvedValue([team('Alfa'), team('Bravo')])
  api.getMultiPlayerStats.mockReset().mockResolvedValue([])
})

describe('MultiPhaseStatsPage on the base components (issue #192)', () => {
  it('has one h1 and starts with every sibling phase combined', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Estadísticas Multifase' })).toBeInTheDocument()
    await waitFor(() => expect(api.getMultiTeamStats).toHaveBeenCalledWith(SIBLINGS, false))
    expect(await screen.findByText('Alfa')).toBeInTheDocument()
  })

  it('the phases are toggle buttons that say whether they are in; leaving one out asks the API for the rest', async () => {
    renderPage()
    const regular = await screen.findByRole('button', { name: 'Unico' })
    const playoffs = screen.getByRole('button', { name: 'Play-offs' })
    expect(regular).toHaveAttribute('aria-pressed', 'true')
    expect(playoffs).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(playoffs)
    expect(screen.getByRole('button', { name: 'Play-offs' })).toHaveAttribute('aria-pressed', 'false')
    await waitFor(() => expect(api.getMultiTeamStats).toHaveBeenLastCalledWith([SIBLINGS[0]], false))
  })

  it('with no phase chosen it says what to do instead of asking for nothing', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Unico' }))
    fireEvent.click(screen.getByRole('button', { name: 'Play-offs' }))
    expect(await screen.findByText(/Selecciona al menos una fase/)).toBeInTheDocument()
  })

  it('teams and players are tabs, and so are basic and advanced; the players are only asked for when their tab is open', async () => {
    renderPage()
    await screen.findByText('Alfa')
    const entities = within(screen.getByRole('tablist', { name: /equipos o jugadores/i })).getAllByRole('tab')
    expect(entities.map(t => t.textContent)).toEqual(['Equipos', 'Jugadores'])
    expect(screen.getByRole('tab', { name: 'Equipos' })).toHaveAttribute('aria-selected', 'true')
    expect(api.getMultiPlayerStats).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('tab', { name: 'Jugadores' }))
    await waitFor(() => expect(api.getMultiPlayerStats).toHaveBeenCalledWith(SIBLINGS, false))
    const kinds = within(screen.getByRole('tablist', { name: /tipo de estadística/i })).getAllByRole('tab')
    expect(kinds.map(t => t.textContent)).toEqual(['Básico', 'Avanzado'])
    expect(within(screen.getByRole('tablist', { name: /tipo de estadística/i })).getByRole('tab', { name: 'Básico' })).toHaveAttribute('aria-selected', 'true')
  })
})
