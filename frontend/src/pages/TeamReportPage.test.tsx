import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeamReportPage from './TeamReportPage'
import { CollectionProvider } from '@/context/CollectionContext'
import * as client from '@/api/client'
import * as api from '@/api/teamReport'

const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const FBCYL = 'FBCYL_1DF_2025_A'

function page(collection: string) {
  vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '10', name: 'Zamora' }] as never)
  const report = vi.spyOn(api, 'getTeamReport').mockResolvedValue({
    team: 'Zamora', mode: 'own', strengths: [], weaknesses: [], zones: [], areas: [], consistency: [], differential: [], sample: { games: 5 },
  } as never)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[`/${collection}/team-report`]}>
        <Routes><Route path="/:collection/team-report" element={<CollectionProvider><TeamReportPage /></CollectionProvider>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>)
  return report
}

afterEach(() => vi.restoreAllMocks())

// Issue #627: the rival scouting has TWO doors in the web. «Scouting del rival» is the complete one (keys, plan, players, comparison, its own PDF) but it is FEB only;
// the rival mode of this page is a poorer subset that also serves FBCYL. In FEB this page is for the own team and points at the other; in FBCYL it keeps both modes.
describe('TeamReportPage (issue #627)', () => {
  it('in FEB there is only the own analysis, and the rival scouting is one link away', async () => {
    const report = page(FEB)
    await screen.findByRole('heading', { level: 1, name: 'Informe de equipo' })
    expect(screen.queryByRole('radiogroup', { name: 'Tipo de informe' })).toBeNull()
    const link = screen.getByRole('link', { name: /Scouting del rival/ })
    expect(link).toHaveAttribute('href', `/${FEB}/scouting-rival`)
    await screen.findByRole('option', { name: 'Zamora' })
    fireEvent.change(screen.getByLabelText('Equipo'), { target: { value: '10' } })
    await waitFor(() => expect(report).toHaveBeenCalledWith(FEB, '10', 'own'))
    expect(report).not.toHaveBeenCalledWith(expect.anything(), expect.anything(), 'rival')
  })

  it('in FBCYL both modes stay, and the rival one says what it is', async () => {
    const report = page(FBCYL)
    await screen.findByRole('heading', { level: 1, name: 'Informe de equipo' })
    expect(screen.getByRole('radiogroup', { name: 'Tipo de informe' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Propio equipo' })).toHaveAttribute('aria-checked', 'true')
    await screen.findByRole('option', { name: 'Zamora' })
    fireEvent.change(screen.getByLabelText('Equipo'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Scouting rival' }))
    await waitFor(() => expect(report).toHaveBeenCalledWith(FBCYL, '10', 'rival'))
    expect(screen.getByText(/versión por reglas/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Scouting del rival/ })).toBeNull()
  })
})
