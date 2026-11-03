import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getElasticityModels: vi.fn().mockResolvedValue({ models: [] }), getBacktesting: vi.fn(), getBacktestingLive: vi.fn(), getElasticityPredictLive: vi.fn(),
  getHistoricalSeasons: vi.fn().mockResolvedValue([]), getHistoricalTeams: vi.fn().mockResolvedValue([]), getLiveTeamNames: vi.fn().mockResolvedValue([]),
}))
vi.mock('@/api/client', async () => ({ ...(await vi.importActual<object>('@/api/client')), ...api }))
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import { ModelsTab } from './ModelsTab'

// The models of the predictive analysis (Elasticidades and Validación) are out of the web with it (the rework): the Admin page no longer shows this tab, but the component is kept and
// still works on its own, so it can come back.
describe('ModelsTab (kept, not shown)', () => {
  it('Elasticidades and Validación are tabs of their own', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={qc}><MemoryRouter><ModelsTab /></MemoryRouter></QueryClientProvider>)
    const sub = screen.getByRole('tablist', { name: /modelos predictivos/i })
    expect(within(sub).getAllByRole('tab').map(t => t.textContent)).toEqual(['Elasticidades', 'Validación'])
    fireEvent.click(within(sub).getByRole('tab', { name: 'Validación' }))
    expect(within(sub).getByRole('tab', { name: 'Validación' })).toHaveAttribute('aria-selected', 'true')
  })
})
