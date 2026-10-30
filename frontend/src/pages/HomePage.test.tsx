import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getCollectionList: vi.fn() }))
vi.mock('@/api/client', () => api)

import HomePage from './HomePage'
import { loadRecents } from '@/lib/recents'

// Issue #666 (U5e): the home on the base components — one h1 (the brand), the competitions are links (they take you to a page), the refresh an icon button
// with its name, the failure a Button. Opening a competition is still remembered in the recents.
const COLLECTIONS = [
  { name: 'LF2_2026_A', league: 'FEB', competition: 'LF2', season: '2026', group: 'A', game_count: 12 },
  { name: 'FBCYL_1A_2026', league: 'FBCYL', competition: '1A', season: '2026', group: '', game_count: 8 },
]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><HomePage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getCollectionList.mockReset().mockResolvedValue(COLLECTIONS)
  try { localStorage.clear() } catch { /* the setup keeps it in memory */ }
})

describe('HomePage on the base components (issue #666)', () => {
  it('has one h1, the brand, and its subtitle', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'BasketLab' })).toBeInTheDocument()
    expect(screen.getByText(/Análisis estadístico de baloncesto/)).toBeInTheDocument()
  })

  it('every competition is a link to its page, and opening it is remembered in the recents', async () => {
    renderPage()
    const link = await screen.findByRole('link', { name: /LF2 2026/ })
    expect(link).toHaveAttribute('href', '/LF2_2026_A')
    expect(within(link).getByText('12 partidos')).toBeInTheDocument()
    fireEvent.click(link)
    expect(loadRecents().map(r => r.name)).toContain('LF2_2026_A')
  })

  it('the refresh of the list is an icon button with its name', async () => {
    renderPage()
    await screen.findByRole('link', { name: /LF2 2026/ })
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar lista' }))
    await waitFor(() => expect(api.getCollectionList).toHaveBeenCalledTimes(2))
  })

  it('a failing server says so and offers to retry', async () => {
    api.getCollectionList.mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText('No se pudo conectar con el servidor.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(api.getCollectionList).toHaveBeenCalledTimes(2))
  })

  it('an empty database sends to the administration', async () => {
    api.getCollectionList.mockResolvedValue([])
    renderPage()
    expect(await screen.findByText('Base de datos vacía')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ir a Administración' })).toHaveAttribute('href', '/admin')
  })
})
