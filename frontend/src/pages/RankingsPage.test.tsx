import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getPlayerStats: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import RankingsPage from './RankingsPage'

const player = (id: string, name: string, minutes: number, points: number) => ({
  player_id: id, player_name: name, team_name: 'Equipo', games_played: 5, minutes_per_game: minutes, points_per_game: points,
})
// the player who scores most is not the one who plays most
const PLAYERS = [player('1', 'Anotador', 18.5, 20), player('2', 'Titular', 31.2, 8), player('3', 'Suplente', 6.0, 2)]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><RankingsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const order = () => screen.getAllByText(/^(Anotador|Titular|Suplente)$/).map(n => n.textContent)

describe('RankingsPage minutes', () => {
  beforeEach(() => api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS))

  it('ranks players by minutes per game when "Minutos" is chosen in the basic stats', async () => {
    renderPage()
    await screen.findByText('Anotador')
    expect(order()).toEqual(['Anotador', 'Titular', 'Suplente'])        // by points, the default
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    expect(order()).toEqual(['Titular', 'Anotador', 'Suplente'])
    expect(screen.getByText('31.2')).toBeTruthy()
  })

  it('still filters by the minimum of minutes per game when ranking by minutes', async () => {
    renderPage()
    await screen.findByText('Anotador')
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    fireEvent.change(within(screen.getByText(/MIN/).closest('label') as HTMLElement).getByRole('spinbutton'), { target: { value: '10' } })
    expect(order()).toEqual(['Titular', 'Anotador'])
  })
})
