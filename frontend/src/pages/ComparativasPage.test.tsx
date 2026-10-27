import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getTeamComparison: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import ComparativasPage from './ComparativasPage'

/** One team of the answer: its figures in each group and the difference the API computes (group A minus group B). */
const team = (name: string, a: Record<string, number>, b: Record<string, number>) => ({
  team_id: name, team_name: name, games_a: 3, games_b: 2, a, b,
  diff: Object.fromEntries(Object.keys(a).filter(k => k in b).map(k => [k, a[k] - b[k]])),
})
const ANSWER = (by = 'venue', labels: [string, string] = ['Local', 'Visitante']) => ({
  by, label_a: labels[0], label_b: labels[1],
  team: [
    team('Alfa', { points_per_game: 85, turnovers_per_game: 14, fg3_percentage: 36.5, offensive_rating: 110 }, { points_per_game: 78, turnovers_per_game: 12, fg3_percentage: 34, offensive_rating: 104 }),
    team('Bravo', { points_per_game: 70, turnovers_per_game: 10, fg3_percentage: 30, offensive_rating: 99 }, { points_per_game: 72.5, turnovers_per_game: 11, fg3_percentage: 33.5, offensive_rating: 101 }),
  ],
  opponent: [
    team('Alfa', { points_per_game: 75, turnovers_per_game: 9 }, { points_per_game: 70, turnovers_per_game: 11 }),
    team('Bravo', { points_per_game: 80, turnovers_per_game: 12 }, { points_per_game: 82, turnovers_per_game: 12 }),
  ],
})

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><ComparativasPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const cellOf = (team: string, header: string) => {
  const table = screen.getByRole('table')
  const col = within(table).getAllByRole('columnheader').findIndex(h => h.textContent?.startsWith(header))
  const tr = within(table).getByText(team).closest('tr') as HTMLElement
  return within(tr).getAllByRole('cell')[col]
}

describe('ComparativasPage: the comparative reports of the weekly report, on the web (issue #607)', () => {
  beforeEach(() => api.getTeamComparison.mockReset().mockImplementation(async (_c: string, by: string) => (
    by === 'result' ? ANSWER('result', ['Ganados', 'Perdidos']) : by === 'period' ? ANSWER('period', ['Tramo', 'Resto de la temporada']) : ANSWER()
  )))
  afterEach(() => vi.useRealTimers())

  it('opens on home vs away and shows each figure with the real difference', async () => {
    renderPage()
    await screen.findByText('Alfa')
    expect(api.getTeamComparison).toHaveBeenCalledWith('LF_CHALLENGE', 'venue', undefined)
    expect(cellOf('Alfa', 'PPP').textContent).toContain('85.0')
    expect(cellOf('Alfa', 'PPP').textContent).toContain('+7.0')
    expect(cellOf('Bravo', 'PPP').textContent).toContain('-2.5')
    expect(cellOf('Bravo', '%T3').textContent).toContain('-3.5')          // percentage points
  })

  it('names both groups of the comparison in the page', async () => {
    renderPage()
    await screen.findByText('Alfa')
    expect(screen.getByText(/Local frente a Visitante/)).toBeInTheDocument()
  })

  it('won vs lost asks for the other comparison', async () => {
    renderPage()
    await screen.findByText('Alfa')
    fireEvent.click(screen.getByRole('button', { name: /Ganados vs perdidos/ }))
    await waitFor(() => expect(api.getTeamComparison).toHaveBeenLastCalledWith('LF_CHALLENGE', 'result', undefined))
    expect(await screen.findByText(/Ganados frente a Perdidos/)).toBeInTheDocument()
  })

  it('a difference is green when it is good and red when it is bad, and the other way round where less is better', async () => {
    renderPage()
    await screen.findByText('Alfa')
    const good = within(cellOf('Alfa', 'PPP')).getByText('+7.0')
    const lessIsBetterUp = within(cellOf('Alfa', 'Perd')).getByText('+2.0')      // more turnovers: bad
    const lessIsBetterDown = within(cellOf('Bravo', 'Perd')).getByText('-1.0')   // fewer turnovers: good
    expect(good.className).toContain('text-brand-400')
    expect(lessIsBetterUp.className).toContain('text-down')
    expect(lessIsBetterDown.className).toContain('text-brand-400')
  })

  it('what the rivals did against each team is its own view, where the good and the bad are swapped', async () => {
    renderPage()
    await screen.findByText('Alfa')
    fireEvent.click(screen.getByRole('button', { name: 'Rivales' }))
    // the rivals scored 5 more points against Alfa at home: that is bad for Alfa, so it is red
    expect(within(cellOf('Alfa', 'PPP')).getByText('+5.0').className).toContain('text-down')
    expect(within(cellOf('Alfa', 'Perd')).getByText('-2.0').className).toContain('text-down')
  })

  it('the advanced figures are one click away', async () => {
    renderPage()
    await screen.findByText('Alfa')
    fireEvent.click(screen.getByRole('button', { name: 'Avanzado' }))
    expect(cellOf('Alfa', 'OER').textContent).toContain('+6.0')
  })

  it('the games of each group are in one column, like the weekly report', async () => {
    renderPage()
    await screen.findByText('Alfa')
    expect(cellOf('Alfa', 'PJ').textContent).toBe('3+2')
  })

  it('no arrow of trend is left', async () => {
    renderPage()
    await screen.findByText('Alfa')
    expect(screen.getByRole('table').textContent).not.toMatch(/[⇈↑≈↓⇊]/)
  })
})

describe('ComparativasPage: a stretch of dates against the rest of the season', () => {
  beforeEach(() => api.getTeamComparison.mockReset().mockResolvedValue(ANSWER('period', ['Tramo', 'Resto de la temporada'])))
  afterEach(() => vi.useRealTimers())

  it('asks nothing until there is a date, and says what to do', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Tramo vs resto/ }))
    expect(await screen.findByText(/Elige un tramo/)).toBeInTheDocument()
    expect(api.getTeamComparison).not.toHaveBeenCalledWith(expect.anything(), 'period', expect.anything())
  })

  it('the shortcut of 30 days is the last 30 days, today included, like the weekly report', async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-27T10:00:00') })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Tramo vs resto/ }))
    fireEvent.click(screen.getByRole('button', { name: /30 días/ }))
    await waitFor(() => expect(api.getTeamComparison).toHaveBeenCalledWith('LF_CHALLENGE', 'period', { from: '2026-09-28', to: '2026-10-27' }))
  })

  it('the shortcut of 15 days and the dates typed by hand ask for their own stretch', async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-10-27T10:00:00') })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Tramo vs resto/ }))
    fireEvent.click(screen.getByRole('button', { name: /15 días/ }))
    await waitFor(() => expect(api.getTeamComparison).toHaveBeenCalledWith('LF_CHALLENGE', 'period', { from: '2026-10-13', to: '2026-10-27' }))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-01' } })
    fireEvent.change(screen.getByLabelText('Hasta'), { target: { value: '2026-10-05' } })
    await waitFor(() => expect(api.getTeamComparison).toHaveBeenLastCalledWith('LF_CHALLENGE', 'period', { from: '2026-10-01', to: '2026-10-05' }))
  })

  it('a stretch open on one side is a stretch too', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Tramo vs resto/ }))
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2026-10-01' } })
    await waitFor(() => expect(api.getTeamComparison).toHaveBeenCalledWith('LF_CHALLENGE', 'period', { from: '2026-10-01' }))
  })
})
