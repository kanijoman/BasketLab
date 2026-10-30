import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getTeamStats: vi.fn(), streamLineupAnalysis: vi.fn(), getPlayerStats: vi.fn(), getInOutAnalysis: vi.fn(),
}))
vi.mock('@/api/client', async () => ({ ...(await vi.importActual<object>('@/api/client')), ...api }))
// one collection object for every render: the page analyses again whenever it changes, so a new one per render would never settle
const collectionState = vi.hoisted(() => ({ value: { name: 'LF', label: 'LF Challenge', isFbcyl: false } }))
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: collectionState.value }),
}))

import InOutPage from './InOutPage'
import LineupsPage from './LineupsPage'

afterEach(cleanup)

function page(client: QueryClient, element: JSX.Element) {
  return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>)
}

describe('LineupsPage: the teams to choose from are there when the page opens (issue #605)', () => {
  beforeEach(() => {
    api.getTeamStats.mockReset().mockResolvedValue({ team_stats: [{ team_name: 'Bravo', team_id: 2 }, { team_name: 'Alfa', team_id: 1 }], opponent_stats: [] })
    api.streamLineupAnalysis.mockReset().mockReturnValue({ cancel: vi.fn() })
    api.getPlayerStats.mockReset().mockResolvedValue([])
    api.getInOutAnalysis.mockReset().mockResolvedValue(null)
  })

  it('offers the teams of the collection', async () => {
    page(new QueryClient({ defaultOptions: { queries: { retry: false } } }), <LineupsPage />)
    expect(await screen.findByRole('option', { name: 'Alfa' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Bravo' })).toBeTruthy()
  })

  it('offers them after visiting the In/Out page in the same session, not only after a refresh of the browser (regression)', async () => {
    // InOutPage turned the team stats into a list of {id, name} under the key LineupsPage used for the whole answer (``{team_stats}``): the next page read an array as the
    // answer, found no ``team_stats`` and offered no team until the refresh of the browser emptied the cache
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const first = page(client, <InOutPage />)
    await vi.waitFor(() => expect(api.getTeamStats).toHaveBeenCalled())
    await vi.waitFor(() => expect(client.isFetching()).toBe(0))
    first.unmount()

    page(client, <LineupsPage />)
    expect(await screen.findByRole('option', { name: 'Alfa' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Bravo' })).toBeTruthy()
  })
})

// Issue #194 (U5c): Combinaciones on the base components — one h1, the buttons of the form are Buttons (the analysis says it is working).
describe('LineupsPage on the base components (issue #194)', () => {
  beforeEach(() => {
    api.getTeamStats.mockReset().mockResolvedValue({ team_stats: [{ team_name: 'Alfa', team_id: 1 }], opponent_stats: [] })
    api.streamLineupAnalysis.mockReset().mockReturnValue(new Promise(() => undefined))
    api.getPlayerStats.mockReset().mockResolvedValue([])
    api.getInOutAnalysis.mockReset().mockResolvedValue(null)
  })

  it('has one h1 with the competition as its subtitle', () => {
    page(new QueryClient(), <LineupsPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Análisis de Combinaciones' })).toBeTruthy()
    expect(screen.getByText('LF Challenge')).toBeTruthy()
  })

  it('"Sin mínimos" waits for a minimum to clear and the analysis button says it is working while it runs', async () => {
    page(new QueryClient(), <LineupsPage />)
    await screen.findByRole('option', { name: 'Alfa' })
    fireEvent.change(screen.getByLabelText('Mín. minutos'), { target: { value: '0' } })
    fireEvent.change(screen.getByLabelText('Mín. partidos'), { target: { value: '0' } })
    expect(screen.getByRole('button', { name: 'Sin mínimos' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Mín. partidos'), { target: { value: '3' } })
    expect(screen.getByRole('button', { name: 'Sin mínimos' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Sin mínimos' }))
    expect(screen.getByLabelText('Mín. partidos')).toHaveValue(0)
    fireEvent.click(screen.getByRole('button', { name: 'Analizar' }))
    const working = await screen.findByRole('button', { name: /Analizando/ })
    expect(working).toHaveAttribute('aria-busy', 'true')
    expect(working).toBeDisabled()
  })
})
