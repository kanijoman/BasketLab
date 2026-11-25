import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getLiveTeamNames: vi.fn(),
  getShotZones: vi.fn(),
  getShotRaw: vi.fn(),
  getPlayerStats: vi.fn(),
  getPlayerQuartiles: vi.fn(),
}))
const current = vi.hoisted(() => ({ collection: { name: 'FBCYL_1A_2026', label: 'FBCYL 1A', isFbcyl: true }, left: new Set<string>() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({ useCollection: () => ({ collection: current.collection }) }))
vi.mock('@/lib/useLeftPlayers', () => ({ useLeftPlayers: () => current.left }))

import ShotChartPage from './ShotChartPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><ShotChartPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ShotChartPage with a FBCYL collection (#150)', () => {
  beforeEach(() => {
    Object.values(api).forEach(f => f.mockReset())
    api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo FBCYL' }])
    api.getShotZones.mockResolvedValue([])
    api.getShotRaw.mockResolvedValue([])
    api.getPlayerStats.mockResolvedValue([])
    api.getPlayerQuartiles.mockResolvedValue({})
  })

  it('is available (no "No disponible para FBCYL" notice) and lists the teams', async () => {
    renderPage()
    await waitFor(() => expect(api.getLiveTeamNames).toHaveBeenCalledWith('FBCYL_1A_2026'))
    expect(screen.queryByText(/No disponible para FBCYL/i)).toBeNull()
    expect(await screen.findByText('Equipo FBCYL')).toBeTruthy()
  })
})

// Issue #194 (U5c): Tiros on the base components. The three choices of a few are named radio groups, the player chip has its icon button, one h1.
describe('ShotChartPage on the base components (issue #194)', () => {
  beforeEach(() => {
    Object.values(api).forEach(f => f.mockReset())
    api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo FBCYL' }])
    api.getShotZones.mockResolvedValue([])
    api.getShotRaw.mockResolvedValue([])
    api.getPlayerStats.mockResolvedValue([])
    api.getPlayerQuartiles.mockResolvedValue({})
  })

  it('has one h1 with the competition as its subtitle', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Gráficos de Tiro' })).toBeInTheDocument()
    expect(screen.getByText('FBCYL 1A')).toBeInTheDocument()
  })

  it('what to see, how to draw it and which shots are named radio groups; the result filter only where it applies', async () => {
    renderPage()
    const see = screen.getByRole('radiogroup', { name: 'Ver por' })
    expect(within(see).getAllByRole('radio').map(r => r.textContent)).toEqual(['Equipo', 'Jugador'])
    expect(within(see).getByRole('radio', { name: 'Equipo' })).toHaveAttribute('aria-checked', 'true')
    const viz = screen.getByRole('radiogroup', { name: 'Visualización' })
    expect(within(viz).getAllByRole('radio').map(r => r.textContent)).toEqual(['Zonas', 'Scatter', 'Calor'])
    expect(screen.queryByRole('radiogroup', { name: 'Resultado del tiro' })).toBeNull()      // zones: no filter by result
    fireEvent.click(within(viz).getByRole('radio', { name: 'Scatter' }))
    const result = screen.getByRole('radiogroup', { name: 'Resultado del tiro' })
    expect(within(result).getAllByRole('radio').map(r => r.textContent)).toEqual(['Todos', 'Aciertos', 'Fallos'])
    fireEvent.click(within(result).getByRole('radio', { name: 'Fallos' }))
    expect(within(screen.getByRole('radiogroup', { name: 'Resultado del tiro' })).getByRole('radio', { name: 'Fallos' })).toHaveAttribute('aria-checked', 'true')
  })
})
// Issue #811: the legend of the zones said «Bajo (<25%) / Medio (25–35%) / Alto (>35%)» but the colour of a bubble is the rating against the league (#760), and the court already draws that
// legend: the page repeated an outdated one under it.
describe('the legend of the zones on the shot chart page (issue #811)', () => {
  beforeEach(() => {
    Object.values(api).forEach(f => f.mockReset())
    api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo FBCYL' }])
    api.getShotZones.mockResolvedValue([])
    api.getShotRaw.mockResolvedValue([])
    api.getPlayerStats.mockResolvedValue([])
    api.getPlayerQuartiles.mockResolvedValue({})
  })

  it('does not show fixed percentage thresholds: the colour is not a percentage but the rating against the league regression', () => {
    renderPage()
    expect(screen.queryByText(/Bajo \(/)).toBeNull()
    expect(screen.queryByText(/Medio \(/)).toBeNull()
    expect(screen.queryByText(/Alto \(/)).toBeNull()
    expect(document.body.textContent).not.toMatch(/25%|35%/)
  })

  it('says what size and colour mean, with the league as the reference', () => {
    renderPage()
    expect(screen.getByText(/tamaño.*volumen.*color.*promedio de la liga/i)).toBeInTheDocument()
  })
})

// Issue #1085 (after #1082): the list of players of Tiros did not hide who has left the team, and only the hook was tested.
describe('the player list of Tiros hides who has left the selected team (#1082, #1085)', () => {
  const player = (id: string, name: string, team: string) => ({
    player_id: id, player_name: name, team_name: team, points_per_game: 10, minutes_per_game: 20, games_played: 5,
    fg2_pct: 50, fg3_pct: 33, two_pt_pct: 50, three_pt_pct: 33,
  })

  it('offers the player who stays, not the one with a baja, and keeps showing the leaver of another team', async () => {
    current.collection = { name: 'LF_ENDESA_2026_2027_Liga_Regular_Único', label: 'LF Endesa', isFbcyl: false }
    current.left = new Set(['2'])
    Object.values(api).forEach(f => f.mockReset())
    api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'ALFA' }])
    api.getShotZones.mockResolvedValue([])
    api.getShotRaw.mockResolvedValue([])
    api.getPlayerQuartiles.mockResolvedValue({})
    api.getPlayerStats.mockResolvedValue([player('1', 'Ana Se Queda', 'ALFA'), player('2', 'Bea Se Fue', 'ALFA'), player('3', 'Eva Otra', 'BRAVO')])
    renderPage()
    fireEvent.click(within(screen.getByRole('radiogroup', { name: 'Ver por' })).getByRole('radio', { name: 'Jugador' }))
    await screen.findByRole('option', { name: 'ALFA' })
    fireEvent.change(screen.getByLabelText('Equipo'), { target: { value: '1' } })
    expect(await screen.findByText('Ana Se Queda')).toBeInTheDocument()
    expect(screen.queryByText('Bea Se Fue')).toBeNull()
    current.collection = { name: 'FBCYL_1A_2026', label: 'FBCYL 1A', isFbcyl: true }
    current.left = new Set()
  })
})
