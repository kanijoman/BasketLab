import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getCollectionList: vi.fn(), deleteCollection: vi.fn(),
  getFebCompetitions: vi.fn(), getFebSeasons: vi.fn(), getFebGroups: vi.fn(),
  getFbcylInit: vi.fn(), getFbcylCategories: vi.fn(), getFbcylCompetitions: vi.fn(),
  postScrapeStart: vi.fn(), getScrapeProgress: vi.fn(),
  getHistoricalProgress: vi.fn(), getHistoricalSummary: vi.fn(), postCompetitionIngest: vi.fn(),
  getElasticityModels: vi.fn(), getBacktesting: vi.fn(), getBacktestingLive: vi.fn(), getElasticityPredictLive: vi.fn(),
  getHistoricalSeasons: vi.fn(), getHistoricalTeams: vi.fn(), getLiveTeamNames: vi.fn(),
}))
vi.mock('@/api/client', async () => ({ ...(await vi.importActual<object>('@/api/client')), ...api }))
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import AdminPage from './AdminPage'

// Issue #195 (U5d): Administración on the base components, one file per tab. One h1, the tabs a tablist, the cascade selects labelled, the buttons that start
// a download say they are working, the seasons to ingest checkboxes named by their text. What each tab asks the API for does not change.
const COLLECTIONS = [{ name: 'LF2_2026', league: 'FEB', competition: 'LF2', season: '2026', group: 'A', game_count: 12 }]
const COMPETITIONS = [{ name: 'LF2', results_url: 'u1' }]
const SEASONS = [{ text: '2025/2026', value: 's1' }, { text: '2024/2025', value: 's2' }]
const GROUPS = [{ text: 'Grupo A', value: 'g1' }]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><AdminPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const openTab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

beforeEach(() => {
  Object.values(api).forEach(f => f.mockReset())
  api.getCollectionList.mockResolvedValue(COLLECTIONS)
  api.getFebCompetitions.mockResolvedValue(COMPETITIONS)
  api.getFebSeasons.mockResolvedValue(SEASONS)
  api.getFebGroups.mockResolvedValue(GROUPS)
  api.getHistoricalSummary.mockResolvedValue([{ league: 'FEB', competition: 'LF2', season: '2024/2025', group: '', match_count: 30 }])
  api.postScrapeStart.mockReturnValue(new Promise(() => undefined))
  api.postCompetitionIngest.mockReturnValue(new Promise(() => undefined))
  api.getHistoricalSeasons.mockResolvedValue([])
  api.getElasticityModels.mockResolvedValue([])
  api.getFbcylInit.mockResolvedValue({ seasons: [], genders: [], territories: [] })
})

describe('AdminPage on the base components (issue #195)', () => {
  it('has one h1 and the five tabs, Colecciones open', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Administración' })).toBeInTheDocument()
    const tabs = within(screen.getByRole('tablist', { name: /secciones de administración/i })).getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Colecciones', 'Descargar FEB', 'Descargar FBCYL', 'Histórico', 'Modelos predictivos'])
    expect(screen.getByRole('tab', { name: 'Colecciones' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Colecciones' }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Descargar FEB' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('Colecciones', () => {
  it('every collection has its own named buttons to open and to delete it', async () => {
    renderPage()
    expect(await screen.findByText('LF2_2026')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Abrir LF2_2026' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Eliminar LF2_2026' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Actualizar/ })).toBeInTheDocument()
  })

  it('deletes only after the confirmation and disables the button while it works', async () => {
    api.deleteCollection.mockReturnValue(new Promise(() => undefined))
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValue(true)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar LF2_2026' }))
    expect(api.deleteCollection).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar LF2_2026' }))
    await waitFor(() => expect(api.deleteCollection).toHaveBeenCalledWith('LF2_2026'))
    expect(screen.getByRole('button', { name: 'Eliminar LF2_2026' })).toBeDisabled()
    confirm.mockRestore()
  })

  it('a failing list says so and offers to retry', async () => {
    api.getCollectionList.mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText('Error al cargar colecciones.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
  })
})

describe('Descargar FEB', () => {
  it('the cascade is labelled, each level waits for the one before and the start button says it is working', async () => {
    renderPage()
    openTab('Descargar FEB')
    expect(screen.getByLabelText('Temporada')).toBeDisabled()
    expect(screen.getByRole('button', { name: /Iniciar descarga/ })).toBeDisabled()
    await screen.findByRole('option', { name: 'LF2' })
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'u1' } })
    await screen.findByRole('option', { name: '2025/2026' })
    fireEvent.change(screen.getByLabelText('Temporada'), { target: { value: 's1' } })
    await screen.findByRole('option', { name: 'Grupo A' })
    fireEvent.change(screen.getByLabelText('Grupo'), { target: { value: 'g1' } })
    fireEvent.click(screen.getByRole('button', { name: /Iniciar descarga/ }))
    await waitFor(() => expect(api.postScrapeStart).toHaveBeenCalledWith(expect.objectContaining({ league: 'FEB' })))
    const working = screen.getByRole('button', { name: /Iniciar descarga/ })
    expect(working).toHaveAttribute('aria-busy', 'true')
    expect(working).toBeDisabled()
  })
})

describe('Histórico', () => {
  it('the seasons to ingest are checkboxes named by their text, all or none from two buttons, and the button counts them', async () => {
    renderPage()
    openTab('Histórico')
    expect(await screen.findByText('Contenido actual de HISTORICAL')).toBeInTheDocument()
    await screen.findByRole('option', { name: 'LF2' })
    fireEvent.change(screen.getByLabelText('Competición'), { target: { value: 'u1' } })
    const first = await screen.findByRole('checkbox', { name: '2025/2026' })
    expect(first).not.toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Todas' }))
    expect(screen.getByRole('checkbox', { name: '2024/2025' })).toBeChecked()
    expect(screen.getByRole('button', { name: /Descargar 2 temporadas \(todos los grupos\)/ })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Ninguna' }))
    expect(screen.getByRole('checkbox', { name: '2025/2026' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: /Descargar\s+temporadas/ })).toBeDisabled()
    fireEvent.click(screen.getByRole('checkbox', { name: '2025/2026' }))
    fireEvent.click(screen.getByRole('button', { name: /Descargar 1 temporada/ }))
    await waitFor(() => expect(api.postCompetitionIngest).toHaveBeenCalledWith(
      { competition_url: 'u1', competition_label: 'LF2', seasons: [{ season_value: 's1', season_label: '2025/2026' }] }))
    expect(screen.getByRole('button', { name: /Descargar 1 temporada/ })).toHaveAttribute('aria-busy', 'true')
  })
})

describe('Modelos predictivos', () => {
  it('Elasticidades and Validación are tabs of their own', async () => {
    renderPage()
    openTab('Modelos predictivos')
    const sub = screen.getByRole('tablist', { name: /modelos predictivos/i })
    expect(within(sub).getAllByRole('tab').map(t => t.textContent)).toEqual(['Elasticidades', 'Validación'])
    fireEvent.click(within(sub).getByRole('tab', { name: 'Validación' }))
    expect(within(sub).getByRole('tab', { name: 'Validación' })).toHaveAttribute('aria-selected', 'true')
  })
})
