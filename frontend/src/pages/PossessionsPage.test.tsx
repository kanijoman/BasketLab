import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const NAME = 'MIPELLETYMAS B.F. LEON CON UN NOMBRE MUY LARGO'

const api = vi.hoisted(() => ({
  getPossessionStats: vi.fn(),
  getTeamConsistency: vi.fn(),
  getPossessionsExportUrl: vi.fn(() => '/export.csv'),
  getPossessionQualityExportUrl: vi.fn(() => '/quality.csv'),
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
    fireEvent.click(screen.getByRole('button', { name: 'Estilo propio' }))
    expect(screen.getByText('Rápidas')).toBeTruthy()
    expect(screen.getByText('Lentas')).toBeTruthy()
    expect(screen.queryByText('DER')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Rival' }))
    expect(screen.getByText('Rápidas')).toBeTruthy()
    expect(document.body.textContent).toContain('0.6')
  })

  it('every view is a real tab that can be pressed again to get back to the summary', async () => {
    renderPage()
    await screen.findByText(NAME)
    fireEvent.click(screen.getByRole('button', { name: 'Estilo propio' }))
    fireEvent.click(screen.getByRole('button', { name: 'Resumen' }))
    expect(screen.getByText('DER')).toBeTruthy()
  })
})
