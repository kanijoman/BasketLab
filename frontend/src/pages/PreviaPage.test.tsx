import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ForecastInputs } from '@/api/forecast'
import { buildGames } from '@/forecast/gameLog'
import { teamFixtures } from '@/forecast/fixtures'
import { lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'

const COLLECTION = 'LF_CHALLENGE_2026_2027_Liga_Regular_Único'
const api = vi.hoisted(() => ({ getForecastInputs: vi.fn() }))
vi.mock('@/api/forecast', () => ({ getForecastInputs: api.getForecastInputs }))
vi.mock('@/context/CollectionContext', () => ({ useCollection: () => ({ collection: { name: 'LF_CHALLENGE_2026_2027_Liga_Regular_Único', label: 'LF Challenge', isFbcyl: false } }) }))

import PreviaPage from './PreviaPage'

// The preview of a match (issue #849) on the REAL LF Challenge of 9/11/2026 (16 teams, 47 results of which 8 are not in the archive, 193 matches still to play): choose a team (our point of view), see
// ITS calendar of matches to play, choose the match, and the analysis is made for that rival and that court.
const f = lfChallenge()
const calendar = lfChallengeCalendar()
const inputs: ForecastInputs = { collection: COLLECTION, competition: f, calendar, gender: 'F' }
const games = buildGames(f.team_rows, calendar)
const ids = [...new Set(games.flatMap(g => [g.home, g.away]))]
const nameOf = (id: string) => games.find(g => g.home === id)?.homeName ?? games.find(g => g.away === id)!.awayName
// a match that is the next one of both of its teams, so that the page opens on it whichever of the two is chosen
const first = calendar.matches.filter(m => m.kind === 'scheduled')
  .find(m => teamFixtures(games, calendar, m.home.id)[0].code === m.code && teamFixtures(games, calendar, m.away.id)[0].code === m.code)!
const [home, away] = [first.home.id, first.away.id]

function Where() {
  return <p data-testid="where">{useLocation().search}</p>
}

function renderPage(entry = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[entry]}><PreviaPage /><Where /></MemoryRouter></QueryClientProvider>)
}
const chooseTeam = async (id: string) => {
  const select = await screen.findByLabelText('Equipo')
  await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1))
  fireEvent.change(select, { target: { value: id } })
}
const fixtureRows = () => screen.getAllByTestId('fixture')

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} unobserve() {} disconnect() {} })           // the chart of the scenarios is drawn by recharts; jsdom has no ResizeObserver
  localStorage.clear()
  api.getForecastInputs.mockReset().mockResolvedValue(inputs)
})

describe('choosing the team', () => {
  it('asks for it first: no calendar and no analysis until there is one', async () => {
    renderPage()
    expect(await screen.findByText('Elige tu equipo para ver sus próximos partidos.')).toBeInTheDocument()
    expect(screen.queryByTestId('fixture')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Pronóstico' })).toBeNull()
  })

  it('lists every team of the competition by name', async () => {
    renderPage()
    const select = await screen.findByLabelText('Equipo')
    await waitFor(() => expect(within(select).getAllByRole('option')).toHaveLength(1 + ids.length))
    expect(within(select).getByRole('option', { name: nameOf(home) })).toBeInTheDocument()
  })

  it('remembers it for the next visit', async () => {
    renderPage()
    await chooseTeam(home)
    await screen.findAllByTestId('fixture')
    expect(JSON.parse(localStorage.getItem(`basketlab.forecast.${COLLECTION}`)!).team).toBe(home)
  })

  it('opens on the remembered team', async () => {
    localStorage.setItem(`basketlab.forecast.${COLLECTION}`, JSON.stringify({ team: home, cuts: [] }))
    renderPage()
    expect(await screen.findAllByTestId('fixture')).not.toHaveLength(0)
    expect((screen.getByLabelText('Equipo') as HTMLSelectElement).value).toBe(home)
  })
})

describe('the calendar of the team', () => {
  it('lists only its matches to play, with the rival and where it is played, and none of anybody else', async () => {
    renderPage()
    await chooseTeam(home)
    const rows = await screen.findAllByTestId('fixture')
    const mine = teamFixtures(games, calendar, home)
    expect(rows).toHaveLength(mine.length)
    expect(mine.length).toBeGreaterThan(10)
    expect(within(rows[0]).getByText(new RegExp(nameOf(away)))).toBeInTheDocument()
    expect(within(rows[0]).getByText(/En casa/)).toBeInTheDocument()
    for (const row of rows) expect(row.textContent).not.toMatch(/Resultado/)
  })

  it('is the same match seen from the other team: the rival is the first one and it is played away', async () => {
    renderPage()
    await chooseTeam(away)
    const rows = await screen.findAllByTestId('fixture')
    expect(within(rows[0]).getByText(new RegExp(nameOf(home)))).toBeInTheDocument()
    expect(within(rows[0]).getByText(/Fuera/)).toBeInTheDocument()
  })

  it('has the next match chosen and the analysis made for it, with the rival and the court', async () => {
    renderPage()
    await chooseTeam(home)
    await screen.findByRole('heading', { name: 'Pronóstico' })
    expect(fixtureRows()[0]).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('where').textContent).toContain(`equipo=${home}`)
    expect(screen.getByTestId('preview-title').textContent).toContain(nameOf(away))
    expect(screen.getByTestId('preview-title').textContent).toContain('En casa')
  })

  it('choosing another match changes the analysis to that rival and that court, and the address says which', async () => {
    renderPage()
    await chooseTeam(home)
    await screen.findByRole('heading', { name: 'Pronóstico' })
    const rows = fixtureRows()
    const second = teamFixtures(games, calendar, home)[1]
    fireEvent.click(rows[1])
    await waitFor(() => expect(screen.getByTestId('preview-title').textContent).toContain(second.rivalName))
    expect(screen.getByTestId('preview-title').textContent).toContain(second.court === 'own' ? 'En casa' : 'Fuera')
    expect(fixtureRows()[1]).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('where').textContent).toContain(`partido=${second.code}`)
  })

  it('takes the view to the analysis when a match is chosen: the list is long on a phone', async () => {
    const scroll = vi.fn()
    Element.prototype.scrollIntoView = scroll
    renderPage()
    await chooseTeam(home)
    await screen.findByRole('heading', { name: 'Pronóstico' })
    fireEvent.click(fixtureRows()[1])
    await waitFor(() => expect(scroll).toHaveBeenCalled())
  })

  it('is restored from the address: the team and the match that it names', async () => {
    const third = teamFixtures(games, calendar, home)[2]
    renderPage(`/?equipo=${home}&partido=${third.code}`)
    await waitFor(() => expect(screen.getByTestId('preview-title').textContent).toContain(third.rivalName))
    expect(fixtureRows()[2]).toHaveAttribute('aria-pressed', 'true')
  })

  it('says so when the team has no matches left', async () => {
    api.getForecastInputs.mockResolvedValue({ ...inputs, calendar: { ...calendar, matches: calendar.matches.filter(m => m.kind === 'result') } })
    renderPage()
    await chooseTeam(home)
    expect(await screen.findByText('No quedan partidos pendientes de este equipo.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Pronóstico' })).toBeNull()
  })
})

describe('the analysis', () => {
  it('has the forecast, the scenarios, the objectives of the match and the matchup, and how it is made', async () => {
    renderPage()
    await chooseTeam(home)
    for (const name of ['Pronóstico', 'Escenarios', 'Objetivos del partido', 'Emparejamiento']) expect(await screen.findByRole('heading', { name })).toBeInTheDocument()
    expect(screen.getByText('Probabilidad de victoria')).toBeInTheDocument()
    expect(screen.getByText('Margen esperado')).toBeInTheDocument()
    expect(screen.getByText('Cómo se calcula')).toBeInTheDocument()
  })

  it('tells the four kinds of game and what each looks like', async () => {
    renderPage()
    await chooseTeam(home)
    for (const title of ['Derrota amplia', 'Derrota ajustada', 'Victoria ajustada', 'Victoria amplia']) expect(await screen.findByText(title)).toBeInTheDocument()
  })

  it('gives the objectives as what happens when it does, never as a promise', async () => {
    renderPage()
    await chooseTeam(home)
    const list = await screen.findByLabelText('Objetivos del partido')
    expect(within(list).getAllByText(/Pasa en 1 de cada 4 partidos como este/).length).toBeGreaterThan(2)
    expect(within(list).getAllByText(/ganamos el \d+ % \(en general, el \d+ %\)/).length).toBeGreaterThan(2)
    expect(list.textContent).not.toMatch(/\+\s*\d[\d,.]*\s*%/)
    expect(within(list).getByText('Ataque')).toBeInTheDocument()
    expect(within(list).getByText('Defensa')).toBeInTheDocument()
  })

  it('has a button to export it', async () => {
    renderPage()
    await chooseTeam(home)
    expect(await screen.findByRole('button', { name: /Exportar/ })).toBeInTheDocument()
  })

  it('warns when a team has played little: low confidence and why', async () => {
    const early = { ...inputs, competition: { ...f, team_rows: f.team_rows.slice(0, 40) }, calendar: { ...calendar, matches: calendar.matches.filter(m => m.kind !== 'result') } }
    api.getForecastInputs.mockResolvedValue(early)
    renderPage()
    await chooseTeam(home)
    expect(await screen.findByText('Confianza baja')).toBeInTheDocument()
    expect(screen.getAllByText(/solo ha jugado|aún no ha jugado/).length).toBeGreaterThan(0)
  })
})

describe('what cannot be shown', () => {
  it('a competition without a calendar published says so, and the preview cannot be made', async () => {
    api.getForecastInputs.mockResolvedValue({ ...inputs, calendar: null })
    renderPage()
    expect(await screen.findByText('Esta competición todavía no tiene el calendario publicado.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Equipo')).toBeNull()
  })

  it('an error of the data is told in plain words', async () => {
    api.getForecastInputs.mockRejectedValue(new Error('La previa y la simulación solo funcionan con los datos publicados.'))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('La previa y la simulación solo funcionan con los datos publicados.')
  })

  it('a team of the address that is not in the competition is ignored: the page asks for a team', async () => {
    renderPage('/?equipo=999999&partido=x')
    expect(await screen.findByText('Elige tu equipo para ver sus próximos partidos.')).toBeInTheDocument()
  })

  it('a match of the address that is not one of the team falls back to its next match', async () => {
    renderPage(`/?equipo=${home}&partido=no-such-match`)
    await screen.findByRole('heading', { name: 'Pronóstico' })
    expect(fixtureRows()[0]).toHaveAttribute('aria-pressed', 'true')
  })
})
