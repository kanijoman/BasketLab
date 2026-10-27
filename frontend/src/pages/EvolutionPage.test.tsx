import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getLiveTeamNames: vi.fn(), getTeamEvolution: vi.fn(), getCompetitionEvolution: vi.fn(),
  getPlayerStats: vi.fn(), getTeamsInCollection: vi.fn(), getPlayerConsistency: vi.fn(),
}))
vi.mock('@/api/client', async () => ({ ...(await vi.importActual<object>('@/api/client')), ...api }))
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF', label: 'LF Challenge', isFbcyl: false } }),
}))

import EvolutionPage from './EvolutionPage'
import PlayerStatsPage from './PlayerStatsPage'

const TEAMS = [{ id: '1', name: 'Alfa' }, { id: '2', name: 'Bravo' }]

afterEach(cleanup)

function page(client: QueryClient, element: JSX.Element) {
  return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>)
}

describe('EvolutionPage: the teams to choose from are there when the page opens (issue #605)', () => {
  beforeEach(() => {
    api.getLiveTeamNames.mockReset().mockResolvedValue(TEAMS)
    api.getTeamEvolution.mockReset().mockResolvedValue([])
    api.getCompetitionEvolution.mockReset().mockResolvedValue([])
    api.getPlayerStats.mockReset().mockResolvedValue([])
    api.getTeamsInCollection.mockReset().mockResolvedValue(['Alfa', 'Bravo'])      // the names as text
    api.getPlayerConsistency.mockReset().mockResolvedValue({})
  })

  it('offers the teams of the collection', async () => {
    page(new QueryClient({ defaultOptions: { queries: { retry: false } } }), <EvolutionPage />)
    expect(await screen.findByRole('button', { name: '+ Alfa' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '+ Bravo' })).toBeTruthy()
  })

  it('offers them after visiting the player stats in the same session, not only after a refresh of the browser (regression)', async () => {
    // Jugadores kept its names as text under the key Evolución used for {id, name}: the next page read strings, drew buttons without a name and the right list only
    // came when the refresh of the browser emptied the cache of the queries
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const first = page(client, <PlayerStatsPage />)
    await vi.waitFor(() => expect(api.getTeamsInCollection).toHaveBeenCalled())
    await vi.waitFor(() => expect(client.isFetching()).toBe(0))
    first.unmount()

    page(client, <EvolutionPage />)
    expect(await screen.findByRole('button', { name: '+ Alfa' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '+ Bravo' })).toBeTruthy()
  })
})
