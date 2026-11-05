import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getCollectionList: vi.fn() }))
vi.mock('@/api/client', () => api)

import HomePage from './HomePage'
import { loadRecents } from '@/lib/recents'
import { DataNotAvailable, DataUnavailable } from '@/datasource/resolve'

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

  // Since #334 there is no server behind the list: the failure says what failed (the published data), never «el servidor»
  it('a failing list says so and offers to retry', async () => {
    api.getCollectionList.mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText('No se pudieron cargar los datos.')).toBeInTheDocument()
    expect(screen.queryByText(/servidor/i)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(api.getCollectionList).toHaveBeenCalledTimes(2))
  })

  it.each([
    ['the files cannot answer', new DataNotAvailable('collections'), /no están disponibles todavía/],
    ['the publication is down (the error of the files says why)', new DataUnavailable('No se pudo conectar con los datos publicados.'), /No se pudo conectar con los datos publicados\./],
  ])('%s: the list shows that message, not a generic one', async (_name, error, message) => {
    api.getCollectionList.mockRejectedValue(error)
    renderPage()
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.queryByText('No se pudieron cargar los datos.')).toBeNull()
  })

  it('an empty database says the data comes from the scheduled refresh and links to no administration', async () => {
    api.getCollectionList.mockResolvedValue([])
    renderPage()
    expect(await screen.findByText('Base de datos vacía')).toBeInTheDocument()
    expect(screen.getByText(/refresco programado/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Administra/ })).toBeNull()
    expect(document.querySelector('a[href="/admin"]')).toBeNull()
  })
})

// Issue #761: the competition is chosen by ámbito → temporada → competición → grupo instead of a list of collections.
describe('HomePage selectors (issue #761)', () => {
  const LIST = [
    { name: 'LF2_2026_A', league: 'FEB', competition: 'LF2', season: '2026', group: 'A', game_count: 12 },
    { name: 'LF2_2026_B', league: 'FEB', competition: 'LF2', season: '2026', group: 'B', game_count: 11 },
    { name: 'LF2_2025_A', league: 'FEB', competition: 'LF2', season: '2025', group: 'A', game_count: 30 },
    { name: 'FBCYL_1A_2026', league: 'FBCYL', competition: '1A', season: '2026', group: '', game_count: 8 },
    { name: 'AND_SEN_2026', league: 'ANDALUCIA', competition: 'Senior', season: '2026', group: '', game_count: 5 },
  ]

  it('preselects the latest season and links to the competition it resolves', async () => {
    api.getCollectionList.mockResolvedValue(LIST)
    renderPage()
    expect(await screen.findByRole('combobox', { name: 'Ámbito' })).toHaveValue('FEB')
    expect(screen.getByRole('combobox', { name: 'Temporada' })).toHaveValue('2026')
    expect(screen.getByRole('link', { name: /LF2 2026/ })).toHaveAttribute('href', '/LF2_2026_A')
  })

  it('the ámbitos come from the data, and the group selector only exists when there is more than one', async () => {
    api.getCollectionList.mockResolvedValue(LIST)
    renderPage()
    const ambito = await screen.findByRole('combobox', { name: 'Ámbito' })
    expect(within(ambito).getAllByRole('option').map(o => o.textContent)).toEqual(['FEB', 'FBCYL', 'ANDALUCIA'])
    expect(screen.getByRole('combobox', { name: 'Grupo' })).toBeInTheDocument()
    fireEvent.change(ambito, { target: { value: 'FBCYL' } })
    expect(screen.queryByRole('combobox', { name: 'Grupo' })).toBeNull()
    expect(screen.getByRole('link', { name: /1A 2026/ })).toHaveAttribute('href', '/FBCYL_1A_2026')
  })

  it('choosing the group changes the competition it opens, and opening it is remembered', async () => {
    api.getCollectionList.mockResolvedValue(LIST)
    renderPage()
    fireEvent.change(await screen.findByRole('combobox', { name: 'Grupo' }), { target: { value: 'B' } })
    const link = screen.getByRole('link', { name: /LF2 2026/ })
    expect(link).toHaveAttribute('href', '/LF2_2026_B')
    fireEvent.click(link)
    expect(loadRecents().map(r => r.name)).toContain('LF2_2026_B')
  })
})

// The collections come named as the publication names them: the selectors show the year, the competition and the phase+group, not the pieces of the slug.
describe('HomePage selectors with the real names of the competitions', () => {
  const REAL = [
    { name: 'PRIMERA_FEB_2026_2027_Liga_Regular_Único', league: 'FEB', competition: 'PRIMERA_FEB', season: '2026_2027_Liga_Regular_Único', group: '', game_count: 40 },
    { name: 'SEGUNDA_FEB_2026_2027_Liga_Regular_A', league: 'FEB', competition: 'SEGUNDA_FEB', season: '2026_2027_Liga_Regular', group: 'A', game_count: 30 },
    { name: 'SEGUNDA_FEB_2026_2027_Liga_Regular_B', league: 'FEB', competition: 'SEGUNDA_FEB', season: '2026_2027_Liga_Regular', group: 'B', game_count: 28 },
  ]

  it('season is the years, competition its name and group the phase with its group', async () => {
    api.getCollectionList.mockResolvedValue(REAL)
    renderPage()
    const season = await screen.findByRole('combobox', { name: 'Temporada' })
    expect(within(season).getAllByRole('option').map(o => o.textContent)).toEqual(['2026/2027'])
    expect(within(screen.getByRole('combobox', { name: 'Competición' })).getAllByRole('option').map(o => o.textContent)).toEqual(['PRIMERA FEB', 'SEGUNDA FEB'])
    fireEvent.change(screen.getByRole('combobox', { name: 'Competición' }), { target: { value: 'SEGUNDA FEB' } })
    expect(within(screen.getByRole('combobox', { name: 'Grupo' })).getAllByRole('option').map(o => o.textContent)).toEqual(['Liga Regular A', 'Liga Regular B'])
    expect(screen.getByRole('link', { name: /SEGUNDA FEB 2026\/2027 · Liga Regular A/ })).toHaveAttribute('href', '/SEGUNDA_FEB_2026_2027_Liga_Regular_A')
  })
})
