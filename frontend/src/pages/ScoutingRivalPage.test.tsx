import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getLiveTeamNames: vi.fn() }))
const scouting = vi.hoisted(() => ({
  getScoutingScopes: vi.fn(),
  getPublishedScouting: vi.fn(),
  startScouting: vi.fn(),
  getScoutingProgress: vi.fn(),
  getScoutingReport: vi.fn(),
  downloadScoutingPdf: vi.fn(),
}))
const collectionState = vi.hoisted(() => ({ value: { name: 'FEB_X', label: 'FEB X', isFbcyl: false } }))
vi.mock('@/api/client', () => api)
vi.mock('@/api/scoutingRival', () => scouting)
vi.mock('@/context/CollectionContext', () => ({ useCollection: () => ({ collection: collectionState.value }) }))

import ScoutingRivalPage from './ScoutingRivalPage'
import { ScopedAccessError } from '@live-package/crypto'
import { loadRights } from '@live-package/rights'

const REPORT = {
  team: { id: '2', name: 'Equipo B' }, own_team: { id: '1', name: 'Equipo A' }, sample_games: 6, low_sample: false, notices: [],
  record: { wins: 4, losses: 2, avg_for: 70.5, avg_against: 64.2, avg_margin: 6.3 },
  profile: ['Ritmo medio: 72,4 posesiones por 40 minutos.'],
  keys: [{ area: 'jugadoras', action: 'neutralize', text: 'Depende de A. ESCOLTA: 31 % de sus puntos.' }],
  plan: { neutralize: [{ text: 'Limitar a A. ESCOLTA', source: 'motor' }], exploit: [{ text: 'Atacar su rebote defensivo', source: 'informe' }] },
  players: [{ id: 'p1', name: 'A. ESCOLTA', games: 6, minutes: 150, pts: 120, pts_per_game: 20, share: 0.31, clutch: { pts: 18, fga: 12 } }],
  alerts: [{ id: 'own_drought', label: 'Sequías de anotación', text: 'Sequías de anotación: 2,0 por partido (en 5 partidos, hacia el minuto 22).' }],
  comparison: [{ key: 'pace', label: 'Ritmo', group: 'Básicas', own_text: '70,0', rival_text: '74,0', advantage: 'rival' }],
  zones: [], lineups: [], quarters: {}, edges: {}, timeouts: {}, games: [], collection: 'FEB_X', origin: [],
}

const ORIGIN = [
  { key: 'pts_off_tov', label: 'Puntos tras pérdida rival', own: 18, conceded: 12, league: 15, own_delta_pct: 20, conceded_delta_pct: -20 },
  { key: 'pts_second_chance', label: 'Puntos de 2.ª oportunidad', own: 9, conceded: 13.5, league: 11, own_delta_pct: -18.2, conceded_delta_pct: 22.7 },
  { key: 'bench_pct', label: '% de puntos del banquillo', own: 33, conceded: null, league: 32, own_delta_pct: 3.1, conceded_delta_pct: null },
]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><ScoutingRivalPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

async function choose(rival = '2', own = '1') {
  await screen.findAllByRole('option', { name: 'Equipo B' })
  fireEvent.change(screen.getByLabelText(/equipo a analizar/i), { target: { value: rival } })
  if (own) fireEvent.change(screen.getByLabelText(/nuestro equipo/i), { target: { value: own } })
  // the page first learns what is published for the rival (the button waits for it; instant when the scouting is not published)
  if (rival !== own) await waitFor(() => expect(screen.getByRole('button', { name: /generar informe/i })).not.toBeDisabled())
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  Object.values({ ...api, ...scouting }).forEach(f => f.mockReset())
  collectionState.value = { name: 'FEB_X', label: 'FEB X', isFbcyl: false }
  api.getLiveTeamNames.mockResolvedValue([{ id: '1', name: 'Equipo A' }, { id: '2', name: 'Equipo B' }, { id: '3', name: 'Equipo C' }])
  scouting.getScoutingScopes.mockResolvedValue([])                            // nothing published: the page works as always
  scouting.getPublishedScouting.mockResolvedValue(null)
  scouting.startScouting.mockResolvedValue({ job_id: 'j1' })
  scouting.getScoutingProgress
    .mockResolvedValueOnce({ status: 'running', current: 4, total: 16, team: 'Equipo B', own_team: 'Equipo A', error: null })
    .mockResolvedValue({ status: 'done', current: 16, total: 16, team: 'Equipo B', own_team: 'Equipo A', error: null })
  scouting.getScoutingReport.mockResolvedValue(REPORT)
  scouting.downloadScoutingPdf.mockResolvedValue(new Blob(['%PDF']))
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() })
})
const realUrl = URL
afterEach(() => {
  vi.useRealTimers()
  vi.stubGlobal('URL', realUrl)                      // not unstubAllGlobals: it would drop the in-memory localStorage of the setup (rights are kept there)
})

describe('ScoutingRivalPage (issue #299)', () => {
  it('lets the user choose ANY team of the competition, and ours is optional', async () => {
    renderPage()
    expect(await screen.findAllByRole('option', { name: 'Equipo C' })).toHaveLength(2)
    expect(screen.getByRole('button', { name: /generar informe/i })).toBeDisabled()
    await choose('3', '')
    expect(screen.getByRole('button', { name: /generar informe/i })).not.toBeDisabled()
  })

  it('has one h1 and, while the report is made, the button says it is working and nothing can be changed (issue #666)', async () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Scouting del rival' })).toBeTruthy()
    await choose()
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    const working = await screen.findByRole('button', { name: /generar informe/i })
    await waitFor(() => expect(working.getAttribute('aria-busy')).toBe('true'))
    expect((working as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText(/equipo a analizar/i) as HTMLSelectElement).disabled).toBe(true)
  })

  it('does not accept the same team as scouted and as ours', async () => {
    renderPage()
    await choose('2', '2')
    expect(screen.getByRole('button', { name: /generar informe/i })).toBeDisabled()
    expect(screen.getByText(/deben ser distintos/i)).toBeTruthy()
  })

  it('generates, shows progress and then the preview with the findings, the plan and the matchup', async () => {
    renderPage()
    await choose()
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await waitFor(() => expect(screen.getByRole('progressbar', { name: /progreso del informe/i })).toBeTruthy())
    expect(scouting.startScouting).toHaveBeenCalledWith({ collection: 'FEB_X', team_id: '2', own_team_id: '1' })
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    expect(await screen.findByRole('heading', { name: 'Equipo B' })).toBeTruthy()
    expect(screen.getByText(/depende de A\. ESCOLTA/i)).toBeTruthy()
    expect(screen.getByText('Limitar a A. ESCOLTA')).toBeTruthy()
    expect(screen.getByText('Atacar su rebote defensivo')).toBeTruthy()
    expect(screen.getByText(/6 partidos/)).toBeTruthy()
    expect(screen.getByText(/sequías de anotación: 2,0 por partido/i)).toBeTruthy()
    expect(screen.getByText('Ritmo')).toBeTruthy()
  })

  it('shows the origin of the points of the team against the league when the report has it (#358)', async () => {
    scouting.getScoutingReport.mockResolvedValue({ ...REPORT, origin: ORIGIN })
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })

    expect(await screen.findByText('Origen de los puntos')).toBeTruthy()
    expect(screen.getByText('Puntos tras pérdida rival')).toBeTruthy()
    expect(screen.getByText('+20 %')).toBeTruthy()           // the team against the league
    expect(screen.getByText('+23 %')).toBeTruthy()           // what it concedes against the league
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)   // the bench has no conceded figure
  })

  it.each([['M', 'Jugadores clave', 'Jugador'], ['F', 'Jugadoras clave', 'Jugadora'], [undefined, 'Jugadores clave', 'Jugador']])(
    'names the key players in the gender of the competition (%s, #495)', async (gender, title, column) => {
      scouting.getScoutingReport.mockResolvedValue({ ...REPORT, gender })
      renderPage()
      await choose('2', '')
      fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
      await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
      expect(await screen.findByText(title)).toBeTruthy()
      expect(screen.getByRole('columnheader', { name: column })).toBeTruthy()
    })

  it('has no origin section when the report has no origin figures', async () => {
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    await screen.findByText('Claves tácticas')

    expect(screen.queryByText('Origen de los puntos')).toBeNull()
  })

  it('without our team it asks for no matchup', async () => {
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await waitFor(() => expect(scouting.startScouting).toHaveBeenCalledWith({ collection: 'FEB_X', team_id: '2' }))
  })

  it('says it when there are few games and shows the notice', async () => {
    scouting.getScoutingReport.mockResolvedValue({ ...REPORT, low_sample: true, sample_games: 2, notices: ['Muestra pequeña: solo 2 partidos con jugada a jugada detrás de estos datos; son orientativos.'] })
    renderPage()
    await choose()
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    expect(await screen.findByText(/muestra pequeña: solo 2 partidos/i)).toBeTruthy()
  })

  it('downloads the PDF, as many times as wanted', async () => {
    renderPage()
    await choose()
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    const button = await screen.findByRole('button', { name: /descargar pdf/i })
    fireEvent.click(button)
    await waitFor(() => expect(scouting.downloadScoutingPdf).toHaveBeenCalledWith('j1'))
    fireEvent.click(button)
    await waitFor(() => expect(scouting.downloadScoutingPdf).toHaveBeenCalledTimes(2))
  })

  it('shows the error of a failed job', async () => {
    scouting.getScoutingProgress.mockReset().mockResolvedValue({ status: 'error', current: 0, total: 0, team: 'Equipo B', own_team: null, error: 'El equipo 2 no tiene partidos con jugada a jugada en la colección' })
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    expect(await screen.findByText(/no tiene partidos con jugada a jugada/i)).toBeTruthy()
  })

  it('shows the error when the job cannot be started', async () => {
    scouting.startScouting.mockRejectedValue(new Error('Ya hay un informe en preparación; espera a que termine'))
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    expect(await screen.findByText(/ya hay un informe en preparación/i)).toBeTruthy()
  })

  it('is FEB only for now', async () => {
    collectionState.value = { name: 'FBCYL_X', label: 'FBCYL X', isFbcyl: true }
    renderPage()
    expect(screen.getByText(/solo para competiciones FEB/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /generar informe/i })).toBeNull()
  })
})

// Issue #638: with the scouting published (dataset `scouting`) the user chooses what to see of the rival — only the league, only the cup or both — like the
// phases of Multifase. The published report has no matchup and no PDF job: with our team chosen, or when nothing is published, the report is generated.
const PUBLISHED = (scope: string, games: number) => ({ ...REPORT, own_team: null, comparison: [], scope, sample_games: games, notices: [`Alcance ${scope}`] })
const invitation = (scope: string) => `bl1.${btoa(JSON.stringify({ s: scope, k: btoa(String.fromCharCode(...new Uint8Array(32).fill(5))), e: null })).replace(/=+$/, '')}`

describe('ScoutingRivalPage: published scouting by scope (issue #638)', () => {
  beforeEach(() => {
    localStorage.clear()
    scouting.getScoutingScopes.mockResolvedValue(['liga', 'copa', 'todo'])
    scouting.getPublishedScouting.mockImplementation(async (_c: string, _t: string, scope: string) => PUBLISHED(scope, scope === 'liga' ? 30 : scope === 'copa' ? 3 : 33))
  })

  it('offers Liga, Copa and Agrupado, starts on the league and reads the published report without generating anything', async () => {
    renderPage()
    await choose('2', '')
    const control = await screen.findByRole('radiogroup', { name: 'Partidos a analizar' })
    expect(control).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Liga' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getAllByRole('radio').map(r => r.textContent)).toEqual(['Liga', 'Copa', 'Agrupado'])
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    expect(await screen.findByText('Alcance liga')).toBeInTheDocument()
    expect(scouting.getPublishedScouting).toHaveBeenCalledWith('FEB_X', '2', 'liga')
    expect(scouting.startScouting).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /descargar pdf/i })).toBeNull()                 // a published report has no job to take the PDF from
  })

  it('changing the scope shows that scope of the same rival at once', async () => {
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await screen.findByText('Alcance liga')
    fireEvent.click(await screen.findByRole('radio', { name: 'Copa' }))
    expect(await screen.findByText('Alcance copa')).toBeInTheDocument()
    expect(scouting.getPublishedScouting).toHaveBeenLastCalledWith('FEB_X', '2', 'copa')
    fireEvent.click(screen.getByRole('radio', { name: 'Agrupado' }))
    expect(await screen.findByText('Alcance todo')).toBeInTheDocument()
  })

  it('a rival without cup games has no selector: only the league is published', async () => {
    scouting.getScoutingScopes.mockResolvedValue(['liga'])
    renderPage()
    await choose('2', '')
    await waitFor(() => expect(scouting.getScoutingScopes).toHaveBeenCalledWith('FEB_X', '2'))
    expect(screen.queryByRole('radiogroup', { name: 'Partidos a analizar' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    expect(await screen.findByText('Alcance liga')).toBeInTheDocument()
  })

  it('with our team chosen the report is generated as always (the matchup needs a pair of teams) and the page says so', async () => {
    renderPage()
    await choose('2', '1')
    expect(await screen.findByText(/se genera en el servidor, con la comparativa/i)).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: 'Partidos a analizar' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await waitFor(() => expect(scouting.startScouting).toHaveBeenCalled())
    expect(scouting.getPublishedScouting).not.toHaveBeenCalled()
  })

  it('when the publication cannot give the report, it is generated as always', async () => {
    scouting.getPublishedScouting.mockResolvedValue(null)
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await waitFor(() => expect(scouting.startScouting).toHaveBeenCalled())
  })

  it('without a key it asks for an invitation, and the one pasted unlocks it without leaving the page', async () => {
    scouting.getPublishedScouting.mockRejectedValueOnce(new ScopedAccessError('No tienes acceso.'))
    renderPage()
    await choose('2', '')
    fireEvent.click(screen.getByRole('button', { name: /generar informe/i }))
    await screen.findByText(/necesita una invitación/i)
    fireEvent.change(screen.getByLabelText('Invitación'), { target: { value: invitation('club:1') } })
    fireEvent.click(screen.getByRole('button', { name: 'Desbloquear' }))
    expect(await screen.findByText('Alcance liga')).toBeInTheDocument()
    expect(loadRights().map(r => r.scope)).toEqual(['club:1'])
  })

  it('choosing another rival forgets the scopes of the previous one', async () => {
    scouting.getScoutingScopes.mockImplementation(async (_c: string, team: string) => (team === '2' ? ['liga', 'copa', 'todo'] : []))
    renderPage()
    await choose('2', '')
    await screen.findByRole('radiogroup', { name: 'Partidos a analizar' })
    fireEvent.change(screen.getByLabelText(/equipo a analizar/i), { target: { value: '3' } })
    await waitFor(() => expect(screen.queryByRole('radiogroup', { name: 'Partidos a analizar' })).toBeNull())
  })
})
