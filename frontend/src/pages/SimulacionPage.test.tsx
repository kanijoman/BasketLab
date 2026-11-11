import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ForecastInputs } from '@/api/forecast'
import { pct } from '@/forecast/copy'
import { buildGames } from '@/forecast/gameLog'
import { buildModel } from '@/forecast/pool'
import { simulateSeason } from '@/forecast/seasonSim'
import { lfChallenge, lfChallengeCalendar } from '@/test/forecastFixtures'

const COLLECTION = 'LF_CHALLENGE_2026_2027_Liga_Regular_Único'
const api = vi.hoisted(() => ({ getForecastInputs: vi.fn() }))
vi.mock('@/api/forecast', () => ({ getForecastInputs: api.getForecastInputs }))
vi.mock('@/context/CollectionContext', () => ({ useCollection: () => ({ collection: { name: 'LF_CHALLENGE_2026_2027_Liga_Regular_Único', label: 'LF Challenge', isFbcyl: false } }) }))

import SimulacionPage from './SimulacionPage'

// The simulation of the league (issue #850) on the REAL LF Challenge calendar of 9/11/2026 (16 teams, 193 matches to play): the table with what is expected of every team, the heat map of the final
// positions, the cut lines the reader draws (no promotion or relegation rules are modelled) and the decisive games of the reader's team. The simulation is seeded with the name of the competition,
// so the test computes the same numbers the page shows.
const f = lfChallenge()
const calendar = lfChallengeCalendar()
const inputs: ForecastInputs = { collection: COLLECTION, competition: f, calendar, gender: 'F' }
const model = buildModel(buildGames(f.team_rows, calendar), f.gender)
const sim = simulateSeason(model, calendar)
const byMean = [...sim.teams.keys()].sort((a, b) => sim.meanPosition[a] - sim.meanPosition[b])
const bestId = sim.teams[byMean[0]]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}><MemoryRouter><SimulacionPage /></MemoryRouter></QueryClientProvider>)
}
const table = async () => within(await screen.findByRole('region', { name: 'Clasificación proyectada' })).getByRole('table')
const addCut = (kind: 'Primeros' | 'Últimos', n: string) => {
  fireEvent.change(screen.getByLabelText('Tipo de línea'), { target: { value: kind === 'Primeros' ? 'top' : 'bottom' } })
  fireEvent.change(screen.getByLabelText('Número de equipos'), { target: { value: n } })
  fireEvent.click(screen.getByRole('button', { name: 'Añadir línea' }))
}
const stored = () => JSON.parse(localStorage.getItem(`basketlab.forecast.${COLLECTION}`) ?? 'null')

beforeEach(() => {
  localStorage.clear()
  api.getForecastInputs.mockReset().mockResolvedValue(inputs)
})

describe('the table of the league', () => {
  it('has every team, best expected position first, with what is expected of each', async () => {
    renderPage()
    const rows = within(await table()).getAllByRole('row')
    expect(rows).toHaveLength(1 + 16)
    expect(within(rows[1]).getByText(sim.names[bestId])).toBeInTheDocument()
    expect(within(rows[1]).getByText(pct(sim.pFirst[byMean[0]], 0))).toBeInTheDocument()
    expect(within(rows[1]).getByText(sim.expectedWins[byMean[0]].toFixed(1).replace('.', ','))).toBeInTheDocument()
  })

  it('says what the simulation is and that no promotion, relegation or play-off rules are modelled', async () => {
    renderPage()
    await table()
    expect(screen.getByText(/No se modelan ascensos, descensos ni playoffs/)).toBeInTheDocument()
    expect(screen.getByText('Cómo se calcula')).toBeInTheDocument()
  })

  it('has a button to export it', async () => {
    renderPage()
    await table()
    expect(screen.getByRole('button', { name: /Exportar/ })).toBeInTheDocument()
  })
})

describe('the heat map of the final positions', () => {
  it('has a row per team and a column per position, and each team adds up to all the seasons', async () => {
    renderPage()
    const map = await screen.findByRole('table', { name: 'Probabilidad de cada puesto final' })
    const rows = within(map).getAllByRole('row')
    expect(rows).toHaveLength(1 + 16)
    expect(within(rows[0]).getAllByRole('columnheader')).toHaveLength(1 + 16)
    for (const row of rows.slice(1)) {
      const cells = within(row).getAllByRole('cell')
      expect(cells).toHaveLength(16)
      expect(cells.reduce((s, c) => s + Number(c.getAttribute('data-p')), 0)).toBeCloseTo(1, 9)
    }
  })

  it('every position is for one team in every season: each column adds up to all the seasons too', async () => {
    renderPage()
    const map = await screen.findByRole('table', { name: 'Probabilidad de cada puesto final' })
    const rows = within(map).getAllByRole('row').slice(1).map(r => within(r).getAllByRole('cell').map(c => Number(c.getAttribute('data-p'))))
    for (let pos = 0; pos < 16; pos++) expect(rows.reduce((s, r) => s + r[pos], 0)).toBeCloseTo(1, 9)
  })
})

describe('the cut lines', () => {
  it('start with none, and adding one gives every team its chance of being inside it', async () => {
    renderPage()
    await table()
    expect(screen.queryByText('Entre los 4 primeros')).toBeNull()
    addCut('Primeros', '4')
    expect(await screen.findByText('Entre los 4 primeros')).toBeInTheDocument()
    const first = within(within(await table()).getAllByRole('row')[1])
    expect(first.getByText(pct(sim.positionCounts[byMean[0]].slice(0, 4).reduce((a, b) => a + b, 0) / sim.n, 0))).toBeInTheDocument()
  })

  it('can be of the last ones too, and are listed to be removed', async () => {
    renderPage()
    await table()
    addCut('Primeros', '4')
    addCut('Últimos', '2')
    expect(await screen.findByText('Entre los 2 últimos')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Quitar la línea Primeros 4' }))
    await waitFor(() => expect(screen.queryByText('Entre los 4 primeros')).toBeNull())
    expect(screen.getByText('Entre los 2 últimos')).toBeInTheDocument()
  })

  it('are remembered in the browser of the reader, per competition, and come back on the next visit', async () => {
    const first = renderPage()
    await table()
    addCut('Primeros', '4')
    await screen.findByText('Entre los 4 primeros')
    expect(stored().cuts).toEqual([{ kind: 'top', n: 4 }])
    first.unmount()
    renderPage()
    expect(await screen.findByText('Entre los 4 primeros')).toBeInTheDocument()
  })

  it('refuse a number that is not a line inside the table, and say so: 0, one that leaves nobody out, or a text', async () => {
    renderPage()
    await table()
    for (const bad of ['0', '16', '17', '', 'x', '2,5']) {
      addCut('Primeros', bad)
      expect(await screen.findByRole('alert')).toHaveTextContent('Escribe un número de equipos entre 1 y 15.')
    }
    expect(stored()?.cuts ?? []).toEqual([])
  })

  it('do not repeat: the same line twice is one', async () => {
    renderPage()
    await table()
    addCut('Primeros', '4')
    addCut('Primeros', '4')
    await screen.findByText('Entre los 4 primeros')
    expect(screen.getAllByText('Entre los 4 primeros')).toHaveLength(1)
    expect(stored().cuts).toEqual([{ kind: 'top', n: 4 }])
  })

  it('are at most four', async () => {
    renderPage()
    await table()
    for (const n of ['1', '2', '3', '4', '5']) addCut('Primeros', n)
    expect(await screen.findByText('Entre los 4 primeros')).toBeInTheDocument()
    expect(screen.queryByText('Entre los 5 primeros')).toBeNull()
    expect(screen.getByRole('alert')).toHaveTextContent('Como mucho cuatro líneas.')
  })
})

describe('the team of the reader and its decisive games', () => {
  it('without a team there are no decisive games: the page asks for one', async () => {
    renderPage()
    await table()
    expect(screen.queryByLabelText('Partidos decisivos')).toBeNull()
    expect(screen.getByText('Elige tu equipo para ver los partidos que más le pueden mover en la tabla.')).toBeInTheDocument()
  })

  it('choosing it marks it in the table, remembers it and lists the matches that move its position the most', async () => {
    renderPage()
    await table()
    fireEvent.change(screen.getByLabelText('Tu equipo'), { target: { value: bestId } })
    const list = await screen.findByLabelText('Partidos decisivos')
    expect(within(list).getAllByTestId('decisive')).toHaveLength(8)
    expect(stored().team).toBe(bestId)
    expect(within(await table()).getByText('tu equipo')).toBeInTheDocument()
  })

  it('uses the team the reader chose in the preview of the match', async () => {
    localStorage.setItem(`basketlab.forecast.${COLLECTION}`, JSON.stringify({ team: bestId, cuts: [] }))
    renderPage()
    expect(await screen.findByLabelText('Partidos decisivos')).toBeInTheDocument()
    expect((screen.getByLabelText('Tu equipo') as HTMLSelectElement).value).toBe(bestId)
  })

  it('tells each result of a decisive match, and with a cut line what it does to its chance', async () => {
    localStorage.setItem(`basketlab.forecast.${COLLECTION}`, JSON.stringify({ team: bestId, cuts: [{ kind: 'top', n: 4 }] }))
    renderPage()
    const first = (await screen.findAllByTestId('decisive'))[0]
    expect(first.textContent).toMatch(/puesto medio/)
    expect(first.textContent).toMatch(/de estar entre los 4 primeros/)
  })
})

describe('what cannot be shown', () => {
  it('a season that is over is its final table: nothing left to play, no decisive games', async () => {
    api.getForecastInputs.mockResolvedValue({ ...inputs, calendar: { ...calendar, matches: calendar.matches.filter(m => m.kind === 'result') } })
    renderPage()
    await table()
    expect(screen.getByText('No quedan partidos por jugar: esta es la clasificación final.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Tu equipo')).toBeNull()
  })

  it('a competition without a calendar published says so', async () => {
    api.getForecastInputs.mockResolvedValue({ ...inputs, calendar: null })
    renderPage()
    expect(await screen.findByText('Esta competición todavía no tiene el calendario publicado.')).toBeInTheDocument()
  })

  it('an error of the data is told in plain words', async () => {
    api.getForecastInputs.mockRejectedValue(new Error('La previa y la simulación solo funcionan con los datos publicados.'))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('La previa y la simulación solo funcionan con los datos publicados.')
  })

  it('a damaged memory of the browser is the defaults', async () => {
    localStorage.setItem(`basketlab.forecast.${COLLECTION}`, '{not json')
    renderPage()
    expect(await table()).toBeInTheDocument()
  })
})
