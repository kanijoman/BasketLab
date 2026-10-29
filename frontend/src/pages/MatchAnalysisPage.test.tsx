import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getMatchList: vi.fn(), getMatchAnalysis: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import MatchAnalysisPage from './MatchAnalysisPage'

// Issue #193 (U5b): Análisis de partido on the base components — one h1 with an icon, the team filter and the match two labelled selects. Choosing a team
// narrows the matches and forgets the one chosen; choosing a match asks for its analysis.
const MATCHES = [
  { match_id: 101, date: '2026-10-04T18:00:00', home_team: 'Alfa', away_team: 'Bravo', home_score: 70, away_score: 65 },
  { match_id: 102, date: '2026-10-11T18:00:00', home_team: 'Charlie', away_team: 'Alfa', home_score: 80, away_score: 61 },
  { match_id: 103, date: '2026-10-18T18:00:00', home_team: 'Bravo', away_team: 'Charlie', home_score: 66, away_score: 68 },
]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><MatchAnalysisPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getMatchList.mockReset().mockResolvedValue(MATCHES)
  api.getMatchAnalysis.mockReset().mockResolvedValue({ home: { team_name: 'Alfa' }, away: { team_name: 'Bravo' }, comparison: [] })
})

describe('MatchAnalysisPage on the base components (issue #193)', () => {
  it('has one h1 with the competition as its subtitle', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Análisis de Partido' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the team filter lists the teams of the matches once each, sorted, and the match list lists every match', async () => {
    renderPage()
    const team = await screen.findByLabelText('Equipo')
    expect(within(team).getAllByRole('option').map(o => o.textContent)).toEqual(['Todos los equipos', 'Alfa', 'Bravo', 'Charlie'])
    expect(within(screen.getByLabelText('Partido')).getAllByRole('option')).toHaveLength(1 + MATCHES.length)
  })

  it('choosing a team narrows the matches and forgets the one chosen', async () => {
    renderPage()
    fireEvent.change(await screen.findByLabelText('Partido'), { target: { value: '101' } })
    await waitFor(() => expect(api.getMatchAnalysis).toHaveBeenCalledWith('LF_CHALLENGE', 101, false))
    fireEvent.change(screen.getByLabelText('Equipo'), { target: { value: 'Charlie' } })
    const options = within(screen.getByLabelText('Partido')).getAllByRole('option').map(o => o.textContent)
    expect(options).toHaveLength(1 + 2)                                             // the two matches of Charlie
    expect(screen.getByLabelText('Partido')).toHaveValue('')
  })

  it('a failing match list says so instead of an empty selector', async () => {
    api.getMatchList.mockReset().mockRejectedValue(new Error('boom'))
    renderPage()
    expect(await screen.findByText('Error al cargar partidos.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Partido')).toBeNull()
  })
})
