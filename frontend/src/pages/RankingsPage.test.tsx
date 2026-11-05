import { fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getPlayerStats: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import RankingsPage from './RankingsPage'

const player = (id: string, name: string, minutes: number, points: number) => ({
  player_id: id, player_name: name, team_name: 'Equipo', games_played: 5, minutes_per_game: minutes, points_per_game: points,
})
// the player who scores most is not the one who plays most
const PLAYERS = [player('1', 'Anotador', 18.5, 20), player('2', 'Titular', 31.2, 8), player('3', 'Suplente', 6.0, 2)]

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><RankingsPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

const order = () => screen.getAllByText(/^(Anotador|Titular|Suplente)$/).map(n => n.textContent)

describe('RankingsPage minutes', () => {
  beforeEach(() => api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS))

  it('ranks players by minutes per game when "Minutos" is chosen in the basic stats', async () => {
    renderPage()
    await screen.findByText('Anotador')
    expect(order()).toEqual(['Anotador', 'Titular', 'Suplente'])        // by points, the default
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    expect(order()).toEqual(['Titular', 'Anotador', 'Suplente'])
    expect(screen.getByText('31.2')).toBeTruthy()
  })

  it('still filters by the minimum of minutes per game when ranking by minutes', async () => {
    renderPage()
    await screen.findByText('Anotador')
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    fireEvent.change(within(screen.getByText(/MIN/).closest('label') as HTMLElement).getByRole('spinbutton'), { target: { value: '10' } })
    expect(order()).toEqual(['Titular', 'Anotador'])
  })
})

// Issue #192 (U5a): Rankings on the base components. The groups are tabs, the stats of the open group toggle buttons that say which is on, the filters
// have names a screen reader reads, and the page has one h1.
describe('RankingsPage on the base components (issue #192)', () => {
  beforeEach(() => api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS))

  it('has one h1 with the competition as its subtitle', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: 'Rankings de Jugadores' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the groups of stats are tabs: Básicas, Tiro and Avanzadas, the open one selected, and choosing one starts on its first stat', async () => {
    renderPage()
    await screen.findByText('Anotador')
    const tabs = within(screen.getByRole('tablist', { name: /grupos de estadísticas/i })).getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Básicas', 'Tiro', 'Avanzadas'])
    expect(screen.getByRole('tab', { name: 'Básicas' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('tab', { name: 'Tiro' }))
    expect(screen.getByRole('tab', { name: 'Tiro' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('button', { name: '% TL' })).toHaveAttribute('aria-pressed', 'true')       // the first of the group
  })

  it('the stat chosen says so, and choosing another moves it', async () => {
    renderPage()
    await screen.findByText('Anotador')
    expect(screen.getByRole('button', { name: 'Puntos' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    expect(screen.getByRole('button', { name: 'Minutos' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Puntos' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('every filter has a name: minutes, games, team and the search of a player', async () => {
    renderPage()
    await screen.findByText('Anotador')
    expect(screen.getByLabelText('Filtrar por equipo')).toBeInTheDocument()
    expect(screen.getByLabelText('Buscar jugador')).toBeInTheDocument()
    expect(screen.getAllByRole('spinbutton')).toHaveLength(2)
  })

  it('the search narrows the ranking to the players that match', async () => {
    renderPage()
    await screen.findByText('Anotador')
    fireEvent.change(screen.getByLabelText('Buscar jugador'), { target: { value: 'titular' } })
    expect(order()).toEqual(['Titular'])
  })
})

// the CSV of the export is a Blob handed to an anchor: the boundary is the browser, a fake records what would be saved
function captureDownloads() {
  const blobs: Blob[] = []
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn((b: Blob) => { blobs.push(b); return 'blob:x' }), revokeObjectURL: vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  return blobs
}
const realUrl = URL
afterEach(() => { vi.stubGlobal('URL', realUrl); vi.restoreAllMocks() })           // not unstubAllGlobals: it would drop the in-memory localStorage of the setup

// Issue #759: Rankings had no export. The CSV is the whole ranking under the filters (not the 30 shown), with the position in the league, and the PNG and the PDF capture the list.
describe('RankingsPage export (issue #759)', () => {
  const MANY = Array.from({ length: 35 }, (_, i) => player(String(i + 1), `Jugadora ${String(i + 1).padStart(2, '0')}`, 20, 40 - i))

  it('offers CSV, PNG and PDF when there is a ranking, and nothing when the filters leave it empty', async () => {
    api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Exportar/ }))
    expect(['CSV', 'PNG', 'PDF'].every(name => screen.getByRole('button', { name }))).toBe(true)
    fireEvent.change(screen.getByPlaceholderText('Buscar jugador…'), { target: { value: 'nadie se llama así' } })
    expect(screen.queryByRole('button', { name: /Exportar/ })).toBeNull()
  })

  it('the CSV is the whole ranking, with the position in the league and the value of the statistic chosen', async () => {
    const blobs = captureDownloads()
    api.getPlayerStats.mockReset().mockResolvedValue(MANY)
    renderPage()
    await screen.findByText('Jugadora 01')
    expect(screen.queryByText('Jugadora 31')).toBeNull()                                  // the page shows the first 30
    fireEvent.click(screen.getByRole('button', { name: /Exportar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'CSV' }))
    const lines = (await blobs[0].text()).split('\n')
    expect(lines[0]).toBe('"Puesto","Jugadora","Equipo","PJ","Puntos","Dif. con el líder"')
    expect(lines).toHaveLength(36)                                                        // the header and the 35 players
    expect(lines[1]).toBe('1,Jugadora 01,Equipo,5,40,0')
    expect(lines[35]).toBe('35,Jugadora 35,Equipo,5,6,-34')
  })

  it('exports under the filters but keeps the position of the league', async () => {
    const blobs = captureDownloads()
    api.getPlayerStats.mockReset().mockResolvedValue(PLAYERS)
    renderPage()
    await screen.findByText('Anotador')
    fireEvent.click(screen.getByRole('button', { name: 'Minutos' }))
    fireEvent.change(screen.getByPlaceholderText('Buscar jugador…'), { target: { value: 'anot' } })
    fireEvent.click(screen.getByRole('button', { name: /Exportar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'CSV' }))
    const lines = (await blobs[0].text()).split('\n')
    expect(lines[0]).toContain('"Minutos"')
    expect(lines.slice(1)).toEqual(['2,Anotador,Equipo,5,18.5,-12.7'])                      // second in minutes, 12.7 behind Titular (31.2)
  })
})
