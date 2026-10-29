import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getPlayerStats: vi.fn(), getTeamsInCollection: vi.fn(), getPlayerConsistency: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import PlayerStatsPage from './PlayerStatsPage'

// Issue #192 (U5a): Estadísticas de jugadores on the components of components/ui — one h1 (PageHeader), the team filter a labelled Select, the views Tabs
// (tablist with the keyboard), the stats of the trend panel toggle buttons that say whether they are on. The behaviour is the page's own.
const player = (id: string, name: string, ppg: number) => ({
  player_id: id, player_name: name, team_name: 'Alfa', games_played: 5, minutes_per_game: 25, points_per_game: ppg, rebounds_per_game: 4, assists_per_game: 3,
  total_pts: ppg * 5,
})
const PLAYERS = [player('1', 'A. UNO', 20), player('2', 'B. DOS', 12), player('3', 'C. TRES', 8)]

function renderPage(url = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}><PlayerStatsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

async function chooseTeam() {
  await screen.findByRole('option', { name: 'Alfa' })
  fireEvent.change(screen.getByLabelText('Filtrar por equipo'), { target: { value: 'Alfa' } })
}

beforeEach(() => {
  api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS)
  api.getTeamsInCollection.mockReset().mockResolvedValue(['Alfa', 'Bravo'])
  api.getPlayerConsistency.mockReset().mockResolvedValue({})
})

describe('PlayerStatsPage on the base components (issue #192)', () => {
  it('has one h1, the competition as its subtitle, and asks for a team before loading any player', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Estadísticas de Jugadores' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
    expect(screen.getByText(/Selecciona un equipo/)).toBeInTheDocument()
    expect(api.getPlayerStats).not.toHaveBeenCalled()
  })

  it('the team filter is a labelled select; choosing a team loads its players', async () => {
    renderPage()
    await chooseTeam()
    expect(await screen.findByText('A. UNO')).toBeInTheDocument()
    expect(api.getPlayerStats).toHaveBeenCalledWith('LF_CHALLENGE', expect.objectContaining({ team: 'Alfa' }))
    expect(screen.getByText('3 jugadores')).toBeInTheDocument()
  })

  it('the views are tabs: a tablist with the three views, the open one selected, and the arrows move between them', async () => {
    renderPage()
    await chooseTeam()
    const list = await screen.findByRole('tablist', { name: /vistas/i })
    const tabs = within(list).getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Básico', 'Avanzado', 'Proyección'])
    expect(screen.getByRole('tab', { name: 'Básico' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Básico' }), { key: 'ArrowRight' })
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Avanzado' })).toHaveAttribute('aria-selected', 'true'))
  })

  it('the stats of the trend panel are toggle buttons that say whether they are on, and pressing one turns it off and on', async () => {
    renderPage('/?from=2026-10-01')
    await chooseTeam()
    const points = await screen.findByRole('button', { name: 'PTS' })
    expect(points).toHaveAttribute('aria-pressed', 'true')                      // the three of the start are on
    fireEvent.click(points)
    expect(screen.getByRole('button', { name: 'PTS' })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'PTS' }))
    expect(screen.getByRole('button', { name: 'PTS' })).toHaveAttribute('aria-pressed', 'true')
  })
})
