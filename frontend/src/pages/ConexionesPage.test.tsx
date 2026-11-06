import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AssistConnections, Receiver } from '@/api/assistConnections'

const api = vi.hoisted(() => ({ getAssistConnections: vi.fn(), getTeamStats: vi.fn() }))
vi.mock('@/api/assistConnections', async () => ({ ...(await vi.importActual<object>('@/api/assistConnections')), getAssistConnections: api.getAssistConnections }))
vi.mock('@/api/client', async () => ({ ...(await vi.importActual<object>('@/api/client')), getTeamStats: api.getTeamStats }))
const collectionState = vi.hoisted(() => ({ isFbcyl: false }))
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: collectionState.isFbcyl } }),
}))

import ConexionesPage from './ConexionesPage'

// Issue #773: who passes, who receives and from which zones the receiver scores, assisted against not assisted.
const receiver = (id: string, name: string, over: Partial<Receiver> = {}): Receiver => ({
  player_id: id, name, received: 0, unassisted: 0, fgm: 0, points: 0, assisted_points: 0, assisted_points_pct: 0, share_pct: 0, assisted_pct: 0,
  zones: [], without_zone: 0, from: [], ...over,
})
const ANALYSIS: AssistConnections = {
  team_id: '1', games: 5, assisted_baskets: 10, total_baskets: 20, assists_total: 12, assists_linked: 10, linked_pct: 83.3, format: 'feb',
  receivers: [
    receiver('a', 'ANA', { received: 6, unassisted: 4, fgm: 10, points: 22, assisted_points: 13, assisted_points_pct: 59.1, share_pct: 60, assisted_pct: 60,
      zones: [{ zone: 'paint', assisted: 4, unassisted: 1, assisted_pct: 80 }, { zone: 'top_three', assisted: 2, unassisted: 3, assisted_pct: 40 }],
      from: [{ player_id: 'b', name: 'BEA', count: 4 }, { player_id: 'c', name: 'CLARA', count: 2 }] }),
    receiver('c', 'CLARA', { received: 4, unassisted: 6, fgm: 10, points: 20, assisted_points: 8, assisted_points_pct: 40, share_pct: 40, assisted_pct: 40,
      zones: [{ zone: 'paint', assisted: 4, unassisted: 6, assisted_pct: 40 }], from: [{ player_id: 'b', name: 'BEA', count: 4 }] }),
    receiver('d', 'DORA', { unassisted: 2, fgm: 2, points: 4 }),
  ],
  passers: [
    { player_id: 'b', name: 'BEA', assists: 8, share_pct: 80, to: [{ player_id: 'a', name: 'ANA', count: 4 }, { player_id: 'c', name: 'CLARA', count: 4 }] },
    { player_id: 'c', name: 'CLARA', assists: 2, share_pct: 20, to: [{ player_id: 'a', name: 'ANA', count: 2 }] },
  ],
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter><ConexionesPage /></MemoryRouter></QueryClientProvider>)
}

const pick = (name: string) => screen.getAllByTestId('receiver-name').find(e => e.textContent === name)!
const rowNames = () => screen.getAllByTestId('receiver-name').map(e => e.textContent)

beforeEach(() => {
  collectionState.isFbcyl = false
  api.getTeamStats.mockReset().mockResolvedValue({ team_stats: [{ team_name: 'Bravo', team_id: 2 }, { team_name: 'Alfa', team_id: 1 }], opponent_stats: [] })
  api.getAssistConnections.mockReset().mockResolvedValue(ANALYSIS)
})

describe('ConexionesPage', () => {
  it('has one h1, picks the first team by name and asks for its connections', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Conexiones de asistencia' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Equipo')).toHaveValue('1'))
    await waitFor(() => expect(api.getAssistConnections).toHaveBeenCalledWith('LF_CHALLENGE', '1'))
  })

  it('lists every receiver, the one with most assisted baskets first, with no minimum', async () => {
    renderPage()
    await screen.findAllByTestId('receiver-name')
    expect(rowNames()).toEqual(['ANA', 'CLARA', 'DORA'])
  })

  it('lets the user choose the order: a click on a column header sorts by it', async () => {
    renderPage()
    await screen.findAllByTestId('receiver-name')
    const sortBy = () => fireEvent.click(within(screen.getByRole('columnheader', { name: /% puntos asistidos/i })).getByRole('button'))
    sortBy()
    const first = rowNames()
    sortBy()
    expect(rowNames()).toEqual([...first].reverse())
  })

  it('says how many assists could be tied to a basket, so the figures are read with their coverage', async () => {
    renderPage()
    expect(await screen.findByText(/10 de 12 asistencias/)).toBeInTheDocument()
    expect(screen.getByText(/83%/)).toBeInTheDocument()
  })

  it('a click on a receiver shows his side: how much of his scoring comes from assists, who feeds him and the zones, assisted against not', async () => {
    const { container } = renderPage()
    await screen.findAllByTestId('receiver-name')
    fireEvent.click(pick('ANA'))
    const detail = await screen.findByRole('region', { name: /ANA/ })
    expect(within(detail).getByText(/60%/)).toBeInTheDocument()                           // of his baskets
    expect(within(detail).getByText(/59%/)).toBeInTheDocument()                           // of his points
    expect(within(detail).getByText('BEA')).toBeInTheDocument()
    expect(within(detail).getByText('CLARA')).toBeInTheDocument()
    expect(container.querySelector('[data-zone="paint"]')).not.toBeNull()
    expect(within(detail).getByText('Con asistencia')).toBeInTheDocument()
    expect(within(detail).getByText('Sin asistencia')).toBeInTheDocument()
  })

  it('the player filter chooses the same detail, and shows him as passer too', async () => {
    renderPage()
    await screen.findAllByTestId('receiver-name')
    fireEvent.change(screen.getByLabelText('Jugador'), { target: { value: 'c' } })
    const detail = await screen.findByRole('region', { name: /CLARA/ })
    expect(within(detail).getByText(/da 2 asistencias/i)).toBeInTheDocument()
  })

  it('a receiver with no assisted basket still opens, saying so instead of drawing an empty court', async () => {
    renderPage()
    await screen.findAllByTestId('receiver-name')
    fireEvent.click(pick('DORA'))
    const detail = await screen.findByRole('region', { name: /DORA/ })
    expect(within(detail).getByText(/no ha anotado con asistencia/i)).toBeInTheDocument()
  })

  it('lists the passers with who they usually find', async () => {
    renderPage()
    const passers = await screen.findByRole('region', { name: /Pasadores/i })
    expect(within(passers).getByText('BEA')).toBeInTheDocument()
    expect(within(passers).getByText(/ANA \(4\)/)).toBeInTheDocument()
  })

  it('warns that the data of FBCYL is annotated by the clubs', async () => {
    collectionState.isFbcyl = true
    renderPage()
    expect(await screen.findByText(/anotado por los clubes/i)).toBeInTheDocument()
  })

  it('a team with no baskets says so instead of showing empty tables', async () => {
    api.getAssistConnections.mockResolvedValue({ ...ANALYSIS, receivers: [], passers: [], total_baskets: 0, assisted_baskets: 0, assists_total: 0, assists_linked: 0, linked_pct: null })
    renderPage()
    expect(await screen.findByText(/sin canastas/i)).toBeInTheDocument()
  })

  it('shows the error of the data source', async () => {
    api.getAssistConnections.mockRejectedValue(new Error('Estos datos no están disponibles'))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent(/no están disponibles/)
  })
})
