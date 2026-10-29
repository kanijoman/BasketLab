import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  getHistoricalSeasons: vi.fn(), getHistoricalTeams: vi.fn(), getLiveTeamNames: vi.fn(), postMonteCarlo: vi.fn(), postGamePrediction: vi.fn(),
  getSeasonProjection: vi.fn(), getPlayerStats: vi.fn(), getPlayerPrediction: vi.fn(),
  getElasticityModels: vi.fn(), getElasticityPredictLive: vi.fn(), getBacktesting: vi.fn(), getBacktestingLive: vi.fn(),
}))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico', label: 'Primera FEB', isFbcyl: false } }),
}))

import PredictivePage from './PredictivePage'

// Issue #193 (U5b): Análisis Predictivo on the base components, split in files of its own. What the four tabs ask the API for does not change: one h1, the tabs a
// tablist, the choices of a few a named group, every control with a name, and each prediction asked only when its inputs are there.
const TEAMS = [{ team_id: '1', team_name: 'Alfa' }, { team_id: '2', team_name: 'Bravo' }]
const LIVE = [{ id: '10', name: 'Zamora' }, { id: '11', name: 'León' }]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><PredictivePage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const openTab = (name: string) => fireEvent.click(screen.getByRole('tab', { name }))

/** The picker shows a skeleton while the teams of the season load: wait for the select, then for the team in it. */
async function chooseHistoricalTeam() {
  await waitFor(() => expect(screen.getByLabelText('Temporada')).toHaveValue('2025-2026'))         // the first season is chosen by the picker, and clears the team
  const select = await screen.findByLabelText('Equipo')
  await within(select).findByRole('option', { name: 'Alfa' })
  fireEvent.change(select, { target: { value: '1' } })
}

beforeEach(() => {
  Object.values(api).forEach(f => f.mockReset())
  api.getHistoricalSeasons.mockResolvedValue(['2025-2026'])
  api.getHistoricalTeams.mockResolvedValue(TEAMS)
  api.getLiveTeamNames.mockResolvedValue(LIVE)
  api.postMonteCarlo.mockResolvedValue({ team_id: '1', season: '2025-2026', n_games: 5, n_simulations: 1000, games: [], projected_wins_mean: 3, projected_wins_std: 1, projected_wins_ci_low: 2, projected_wins_ci_high: 4 })
  api.postGamePrediction.mockResolvedValue({ win_prob: 0.62, ci_low: 0.5, ci_high: 0.7, feature_importances: {}, feature_coefficients: {}, n_train: 20, accuracy: 0.7 })
  api.getSeasonProjection.mockResolvedValue([])
  api.getPlayerStats.mockResolvedValue([])
  api.getPlayerPrediction.mockResolvedValue({})
})

describe('PredictivePage on the base components (issue #193)', () => {
  it('has one h1 and four tabs, the Monte Carlo projection open', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Análisis Predictivo' })).toBeInTheDocument()
    const tabs = within(screen.getByRole('tablist', { name: /secciones del análisis predictivo/i })).getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Proyección MC', 'Predicción Partido', 'Predicción Jugador', 'Clasificación Final'])
    expect(screen.getByRole('tab', { name: 'Proyección MC' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Proyección MC' }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Predicción Partido' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('Proyección MC', () => {
  it('chooses the source of the data in a named group and simulates only with a season and a team', async () => {
    renderPage()
    const source = screen.getByRole('radiogroup', { name: 'Fuente de datos' })
    expect(within(source).getAllByRole('radio').map(r => r.textContent)).toEqual(['Temporadas anteriores', 'Temporada actual'])
    expect(within(source).getByRole('radio', { name: 'Temporadas anteriores' })).toHaveAttribute('aria-checked', 'true')
    const simulate = screen.getByRole('button', { name: 'Simular' })
    expect(simulate).toBeDisabled()
    await chooseHistoricalTeam()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Simular' })).toBeEnabled())
    fireEvent.change(screen.getByLabelText('Partidos a proyectar'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Simulaciones'), { target: { value: '500' } })
    fireEvent.click(screen.getByRole('button', { name: 'Simular' }))
    await waitFor(() => expect(api.postMonteCarlo).toHaveBeenCalledWith('1', { n_games: 7, n_simulations: 500, season: '2025-2026' }))
  })

  it('with the current season it asks for the team of the collection and sends it as live', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('radio', { name: 'Temporada actual' }))
    await screen.findByRole('option', { name: 'Zamora' })
    fireEvent.change(screen.getByLabelText('Equipo (temporada actual)'), { target: { value: '10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Simular' }))
    await waitFor(() => expect(api.postMonteCarlo).toHaveBeenCalledWith('10', expect.objectContaining({ live_collection: 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico', live_team_id: '10' })))
  })

  it('says why a simulation failed', async () => {
    api.postMonteCarlo.mockRejectedValue(new Error('Sin partidos suficientes'))
    renderPage()
    await chooseHistoricalTeam()
    fireEvent.click(await screen.findByRole('button', { name: 'Simular' }))
    expect(await screen.findByText('Sin partidos suficientes')).toBeInTheDocument()
  })
})

describe('Predicción Partido', () => {
  it('chooses the season of the model in a named group and predicts with the field and the net rating of the rival', async () => {
    renderPage()
    openTab('Predicción Partido')
    const mode = await screen.findByRole('radiogroup', { name: 'Temporada del modelo' })
    expect(within(mode).getAllByRole('radio').map(r => r.textContent)).toEqual(['Temporada histórica', 'Temporada actual'])
    await screen.findByLabelText('Equipo')
    await screen.findByRole('option', { name: 'Alfa' })
    await waitFor(() => expect(screen.getByLabelText('Equipo')).toHaveValue('1'))                      // the first team is chosen by the tab
    fireEvent.change(screen.getByLabelText('Campo'), { target: { value: 'away' } })
    fireEvent.change(screen.getByLabelText('Net Rtg rival'), { target: { value: '4.5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Predecir' }))
    await waitFor(() => expect(api.postGamePrediction).toHaveBeenCalledWith('1', { season: '2025-2026', is_home: false, opp_net_rtg: 4.5 }))
  })

  it('with the current season it predicts with the team of the collection', async () => {
    renderPage()
    openTab('Predicción Partido')
    fireEvent.click(await screen.findByRole('radio', { name: 'Temporada actual' }))
    await screen.findByRole('option', { name: 'Zamora' })
    fireEvent.click(screen.getByRole('button', { name: 'Predecir' }))
    await waitFor(() => expect(api.postGamePrediction).toHaveBeenCalledWith('_live', expect.objectContaining({ live_team_id: '10', is_home: true, opp_net_rtg: 0 })))
  })
})

describe('Clasificación Final', () => {
  it('projects the end of the season with the games per season chosen', async () => {
    renderPage()
    openTab('Clasificación Final')
    fireEvent.change(await screen.findByLabelText('Partidos/temporada'), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: 'Proyectar' }))
    await waitFor(() => expect(api.getSeasonProjection).toHaveBeenCalled())
    expect(JSON.stringify(api.getSeasonProjection.mock.calls[0])).toContain('30')
  })
})

describe('Predicción Jugador', () => {
  it('asks for a team, then a player, and predicts only with a player chosen', async () => {
    api.getPlayerStats.mockResolvedValue([{ player_id: 'p1', player_name: 'A. UNO', team_name: 'Zamora' }])
    renderPage()
    openTab('Predicción Jugador')
    expect(await screen.findByLabelText('Equipo')).toBeInTheDocument()
    expect(screen.getByLabelText('Jugador')).toBeInTheDocument()
    expect(screen.getByLabelText('Local / Visitante')).toBeInTheDocument()
    expect(screen.getByLabelText('Net Rtg rival')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Predecir' })).toBeDisabled()
  })
})
