import { render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getTeamStats: vi.fn(), getTeamQuartiles: vi.fn(), getTeamConsistency: vi.fn(), getRivalAdjusted: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import TeamStatsPage from './TeamStatsPage'

const NAMES = ['Alfa', 'Bravo', 'Charlie', 'Delta', 'Eco', 'Foxtrot', 'Golf', 'Hotel']
/** A row with the figures the table colours; ``ppg`` is what tells the teams apart. */
const row = (name: string, ppg: number) => ({
  team_name: name, team_id: name, total_games: 5, games_home: 3, games_away: 2, points_per_game: ppg, points_against_per_game: 70,
})
const rows = (base: number) => NAMES.map((n, i) => row(n, base + i))

/** The thresholds of the WHOLE league, with every game of the season: lower than the figures of a filtered table of winners. */
const LEAGUE_QUARTILES = { points_per_game: { q1: 60, q2: 65, q3: 70 }, points_against_per_game: { q1: 60, q2: 65, q3: 70 } }

function renderPage(url = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}><TeamStatsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

/** The quartile class of the points-per-game cell of each team, in the order of the table. */
function colours(): string[] {
  return NAMES.map(name => {
    const tr = screen.getByText(name).closest('tr') as HTMLElement
    const cell = within(tr).getAllByRole('cell').find(c => /table-cell-q\d/.test(c.className)) as HTMLElement | undefined
    return (cell?.className.match(/table-cell-q\d/) ?? ['none'])[0]
  })
}

const count = (list: string[]) => list.reduce<Record<string, number>>((acc, c) => ({ ...acc, [c]: (acc[c] ?? 0) + 1 }), {})

describe('TeamStatsPage: the colours of the quartiles follow the table that is shown (issue #601)', () => {
  beforeEach(() => {
    api.getTeamStats.mockReset().mockResolvedValue({ team_stats: rows(80), opponent_stats: rows(70) })
    api.getTeamQuartiles.mockReset().mockResolvedValue(LEAGUE_QUARTILES)
    api.getTeamConsistency.mockReset().mockResolvedValue({ own: {}, rival: {} })
    api.getRivalAdjusted.mockReset().mockResolvedValue({})
  })

  it('a filtered table (only the wins) is split in four equal groups, not thrown into one by the thresholds of the whole season', async () => {
    renderPage('/?result=won')
    await screen.findByText('Alfa')
    // the winners score 80-87 points: against the league thresholds (60/65/70) all of them would be «best»
    expect(count(colours())).toEqual({ 'table-cell-q1': 2, 'table-cell-q2': 2, 'table-cell-q3': 2, 'table-cell-q4': 2 })
  })

  it('the best of the shown table is green and the worst red, whatever the filter', async () => {
    renderPage('/?result=lost')
    await screen.findByText('Alfa')
    const classes = colours()
    expect(classes[7]).toBe('table-cell-q1')           // the most points per game
    expect(classes[0]).toBe('table-cell-q4')
  })

  it('the filters are what the table asks for, and the quartiles of the whole league are no longer asked', async () => {
    renderPage('/?result=won&venue=home&from=2026-10-01')
    await screen.findByText('Alfa')
    await waitFor(() => expect(api.getTeamStats).toHaveBeenCalledWith('LF_CHALLENGE', expect.objectContaining({ result: 'won', venue: 'home', from: '2026-10-01' })))
    expect(api.getTeamQuartiles).not.toHaveBeenCalled()
  })

  it('lower is better for the points against: the team that concedes least is green', async () => {
    api.getTeamStats.mockResolvedValue({ team_stats: NAMES.map((n, i) => ({ ...row(n, 80), points_against_per_game: 60 + i })), opponent_stats: [] })
    renderPage('/?result=won')
    await screen.findByText('Alfa')
    const tr = screen.getByText('Alfa').closest('tr') as HTMLElement
    const cells = within(tr).getAllByRole('cell').filter(c => /table-cell-q\d/.test(c.className))
    expect(cells.some(c => c.className.includes('table-cell-q1'))).toBe(true)
  })

  it('fewer than four teams are not coloured (nothing to split)', async () => {
    api.getTeamStats.mockResolvedValue({ team_stats: rows(80).slice(0, 3), opponent_stats: [] })
    renderPage('/?result=won')
    await screen.findByText('Alfa')
    expect(document.querySelector('[class*="table-cell-q"]')).toBeNull()
  })
})
