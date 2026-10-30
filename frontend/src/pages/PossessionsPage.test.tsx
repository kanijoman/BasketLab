import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const NAME = 'MIPELLETYMAS B.F. LEON CON UN NOMBRE MUY LARGO'

const api = vi.hoisted(() => ({
  getPossessionStats: vi.fn(),
  getTeamConsistency: vi.fn(),
  fetchPossessionsCsv: vi.fn(),
  fetchPossessionQualityCsv: vi.fn(),
}))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import PossessionsPage from './PossessionsPage'

const STAT = {
  team_name: NAME, team_id: '1008631', total_games: 4, possessions_per_game: 72, points_per_100: 98, oer: 98.2, der: 95.1,
  pace: 71.8, net_rating: 3.1, avg_duration: 14.2, pct_fast: 20, pct_medium: 50, pct_slow: 30,
  oer_fast: 110, oer_medium: 100, oer_slow: 90, est_possessions_per_game: 70, rival_pct_fast: 18, rival_pct_medium: 52,
  rival_pct_slow: 30, rival_oer_fast: 105, rival_oer_medium: 98, rival_oer_slow: 92, rival_avg_duration: 14.8,
  rival_avg_duration_general: 14.9, rival_pace_differential: 0.6,
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><PossessionsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PossessionsPage table', () => {
  beforeEach(() => {
    api.getPossessionStats.mockReset().mockResolvedValue([STAT])
    api.getTeamConsistency.mockReset().mockResolvedValue({ own: {} })
  })

  it('opens on the summary view with the full team name available', async () => {
    renderPage()
    const label = await screen.findByText(NAME)
    expect(label).toHaveAttribute('title', NAME)
    expect(screen.getByText('DER')).toBeTruthy()
    expect(screen.queryByText('Rápidas')).toBeNull()
  })

  it('switches to the own-style view (grouped fast/medium/slow) and to the rival one', async () => {
    renderPage()
    await screen.findByText(NAME)
    fireEvent.click(screen.getByRole('radio', { name: 'Estilo propio' }))
    expect(screen.getByText('Rápidas')).toBeTruthy()
    expect(screen.getByText('Lentas')).toBeTruthy()
    expect(screen.queryByText('DER')).toBeNull()
    fireEvent.click(screen.getByRole('radio', { name: 'Rival' }))
    expect(screen.getByText('Rápidas')).toBeTruthy()
    expect(document.body.textContent).toContain('0.6')
  })

  it('the views of the table are a group of radios: choosing the summary again gets back to it', async () => {
    renderPage()
    await screen.findByText(NAME)
    fireEvent.click(screen.getByRole('radio', { name: 'Estilo propio' }))
    fireEvent.click(screen.getByRole('radio', { name: 'Resumen' }))
    expect(screen.getByText('DER')).toBeTruthy()
  })
})

// Issue #192 (U5a): the page on the base components — one h1, the three parts of the analysis as tabs, the views of the table a named group.
describe('PossessionsPage on the base components (issue #192)', () => {
  beforeEach(() => {
    api.getPossessionStats.mockReset().mockResolvedValue([STAT])
    api.getTeamConsistency.mockReset().mockResolvedValue({ own: {} })
  })

  it('has one h1 with the competition as its subtitle and the two exports as buttons (#679)', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Análisis de Posesiones' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Exportar CSV' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Calidad PBP CSV' })).toBeEnabled()
  })

  it('the table and the two scatters are tabs, the table open, and the arrows move between them', async () => {
    vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })           // the scatter is drawn by recharts; jsdom has no ResizeObserver
    renderPage()
    await screen.findByText(NAME)
    const tabs = within(screen.getByRole('tablist', { name: /partes del análisis/i })).getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Tabla', 'Scatter Ritmo × OER', 'Scatter % Rápidas × OER'])
    expect(screen.getByRole('tab', { name: 'Tabla' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Tabla' }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Scatter Ritmo × OER' })).toHaveAttribute('aria-selected', 'true')
  })

  it('the views of the table are a named group of three options, the summary chosen', async () => {
    renderPage()
    await screen.findByText(NAME)
    const group = screen.getByRole('radiogroup', { name: 'Vista de la tabla' })
    expect(within(group).getAllByRole('radio').map(r => r.textContent)).toEqual(['Resumen', 'Estilo propio', 'Rival'])
    expect(within(group).getByRole('radio', { name: 'Resumen' })).toHaveAttribute('aria-checked', 'true')
  })
})

// Issue #679: the two exports are buttons that make the file (from the published text or the API's file) instead of links to the API.
describe('PossessionsPage exports', () => {
  let downloads: { name: string; href: string }[]
  beforeEach(() => {
    api.getPossessionStats.mockReset().mockResolvedValue([STAT])
    api.getTeamConsistency.mockReset().mockResolvedValue({ own: {} })
    api.fetchPossessionsCsv.mockReset().mockResolvedValue(new Blob(['a,b\n1,2\n']))
    api.fetchPossessionQualityCsv.mockReset().mockResolvedValue(new Blob(['q\n']))
    downloads = []
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:csv')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { downloads.push({ name: this.download, href: this.href }) })
  })

  it('«Exportar CSV» and «Calidad PBP CSV» are buttons, and each downloads its file with the name of the competition', async () => {
    renderPage()
    await screen.findByText(NAME)
    expect(screen.queryByRole('link', { name: 'Exportar CSV' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }))
    await waitFor(() => expect(downloads).toEqual([{ name: 'posesiones_LF_CHALLENGE.csv', href: 'blob:csv' }]))
    expect(api.fetchPossessionsCsv).toHaveBeenCalledWith('LF_CHALLENGE')
    fireEvent.click(screen.getByRole('button', { name: 'Calidad PBP CSV' }))
    await waitFor(() => expect(downloads.map(d => d.name)).toEqual(['posesiones_LF_CHALLENGE.csv', 'calidad_pbp_LF_CHALLENGE.csv']))
  })

  it('says so when the file cannot be made, and the button works again', async () => {
    api.fetchPossessionsCsv.mockRejectedValueOnce(new Error('No se pudo descargar el fichero'))
    renderPage()
    await screen.findByText(NAME)
    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }))
    expect(await screen.findByText('No se pudo descargar el fichero')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Exportar CSV' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }))
    await waitFor(() => expect(downloads).toHaveLength(1))
    expect(screen.queryByText('No se pudo descargar el fichero')).toBeNull()
  })
})
