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

// Issue #192 (U5a): Rankings on the base components. The groups are tabs, the stats of the open group toggle buttons that say which is on, the filters
// have names a screen reader reads, and the page has one h1.
describe('RankingsPage on the base components (issue #192)', () => {
  beforeEach(() => api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS))

  it('has one h1 with the competition as its subtitle', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Rankings de Jugadores' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the groups of stats are tabs: Básicas, Tiro and Avanzadas, the open one selected, and choosing one starts on its first stat', async () => {
    renderPage()
    await screen.findByText('Anotador')
    const tabs = within(screen.getByRole('tablist', { name: /grupos de estadísticas/i })).getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Básicas', 'Tiro', 'Avanzadas'])
    expect(screen.getByRole('tab', { name: 'Básicas' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('tab', { name: 'Tiro' }))
    expect(screen.getByRole('tab', { name: 'Tiro' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('button', { name: '% TL' })).toHaveAttribute('aria-pressed', 'true')       // the first of the group
  })

  it('the stat chosen says so, and choosing another moves it', async () => {
    renderPage()
    await screen.findByText('Anotador')
    expect(screen.getByRole('button', { name: 'Puntos' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    expect(screen.getByRole('button', { name: 'Minutos' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Puntos' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('every filter has a name: minutes, games, team and the search of a player', async () => {
    renderPage()
    await screen.findByText('Anotador')
    expect(screen.getByLabelText('Filtrar por equipo')).toBeInTheDocument()
    expect(screen.getByLabelText('Buscar jugador')).toBeInTheDocument()
    expect(screen.getAllByRole('spinbutton')).toHaveLength(2)
  })

  it('the search narrows the ranking to the players that match', async () => {
    renderPage()
    await screen.findByText('Anotador')
    fireEvent.change(screen.getByLabelText('Buscar jugador'), { target: { value: 'titular' } })
    expect(order()).toEqual(['Titular'])
  })
})
