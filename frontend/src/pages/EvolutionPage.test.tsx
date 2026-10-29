import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
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

// Issue #193 (U5b): Evolución on the base components — one h1, the metric a labelled select, the window of the average a named group, the series
// checkboxes with a name, and the chips of the chosen teams removable by a button that says which team it removes.
describe('EvolutionPage on the base components (issue #193)', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })           // a chosen team draws the chart (recharts); jsdom has no ResizeObserver
    api.getLiveTeamNames.mockReset().mockResolvedValue(TEAMS)
    api.getTeamEvolution.mockReset().mockResolvedValue([])
    api.getCompetitionEvolution.mockReset().mockResolvedValue([])
  })

  const open = () => page(new QueryClient({ defaultOptions: { queries: { retry: false } } }), <EvolutionPage />)

  it('has one h1 with the competition as its subtitle', async () => {
    open()
    expect(await screen.findByRole('heading', { level: 1, name: 'Evolución Temporal' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the metric is a labelled select with its groups, and changing it asks for that metric', async () => {
    open()
    await screen.findByRole('button', { name: '+ Alfa' })
    fireEvent.click(screen.getByRole('button', { name: '+ Alfa' }))
    const select = screen.getByLabelText('Métrica') as HTMLSelectElement
    expect(select.querySelectorAll('optgroup').length).toBeGreaterThan(1)
    const other = Array.from(select.options).find(o => o.value !== select.value)!.value
    fireEvent.change(select, { target: { value: other } })
    await vi.waitFor(() => expect(api.getTeamEvolution).toHaveBeenLastCalledWith('LF', '1', other, expect.any(Number)))
  })

  it('the window of the moving average is a named group of options with the chosen one marked, and choosing another asks for it', async () => {
    open()
    fireEvent.click(await screen.findByRole('button', { name: '+ Alfa' }))
    const group = screen.getByRole('radiogroup', { name: 'Media móvil' })
    const options = within(group).getAllByRole('radio')
    expect(options.length).toBeGreaterThan(1)
    const chosen = options.find(o => o.getAttribute('aria-checked') === 'true')!
    const other = options.find(o => o !== chosen)!
    fireEvent.click(other)
    expect(other).toHaveAttribute('aria-checked', 'true')
    await vi.waitFor(() => expect(api.getTeamEvolution).toHaveBeenLastCalledWith('LF', '1', expect.any(String), Number(other.textContent?.replace('J', ''))))
  })

  it('the series are checkboxes with a name; the league ones ask for the competition only when they are on', async () => {
    open()
    await screen.findByRole('button', { name: '+ Alfa' })
    expect(screen.getByRole('checkbox', { name: 'Por partido' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Media móvil' })).toBeInTheDocument()
    expect(api.getCompetitionEvolution).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('checkbox', { name: /Liga media móvil/ }))
    await vi.waitFor(() => expect(api.getCompetitionEvolution).toHaveBeenCalled())
  })

  it('a chosen team is a chip that says which team the button removes, and removing it offers it again', async () => {
    open()
    fireEvent.click(await screen.findByRole('button', { name: '+ Alfa' }))
    const remove = await screen.findByRole('button', { name: 'Quitar Alfa' })
    fireEvent.click(remove)
    expect(await screen.findByRole('button', { name: '+ Alfa' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Quitar Alfa' })).toBeNull()
  })
})
