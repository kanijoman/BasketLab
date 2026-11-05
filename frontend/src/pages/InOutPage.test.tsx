import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getPlayerStats: vi.fn(), getTeamStats: vi.fn(), getInOutAnalysis: vi.fn() }))
vi.mock('@/api/client', () => api)
vi.mock('@/context/CollectionContext', () => ({
  useCollection: () => ({ collection: { name: 'LF_CHALLENGE', label: 'LF Challenge', isFbcyl: false } }),
}))

import InOutPage from './InOutPage'

// Issue #194 (U5c): IN/OUT on the base components — one h1 with the competition as its subtitle and the two views as tabs (with the keyboard).
function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter><InOutPage /></MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getPlayerStats.mockReset().mockResolvedValue([])
  api.getTeamStats.mockReset().mockResolvedValue([])
  api.getInOutAnalysis.mockReset().mockResolvedValue(null)
})

// Issue #711: the table lists an FBCYL player by the actorId of one game; the analysis looks for his uuid, so the page asks for that.
describe('InOutPage: an FBCYL player (issue #711)', () => {
  it('asks for the analysis with his uuid', async () => {
    const uuid = '593291b9-ff22-4545-b7b3-88159242a0d8'
    api.getPlayerStats.mockResolvedValue([{ player_id: '872552', player_uuid: uuid, player_name: 'F. NUEVO', team_name: 'Alfa', team_id: '1', games_played: 3 }])
    renderPage()
    await screen.findByRole('option', { name: /F\. NUEVO/ })
    fireEvent.change(screen.getByLabelText('Jugador'), { target: { value: uuid } })
    await waitFor(() => expect(api.getInOutAnalysis).toHaveBeenCalledWith('LF_CHALLENGE', uuid))
  })
})

describe('InOutPage on the base components (issue #194)', () => {
  it('has one h1 with the competition as its subtitle', () => {
    renderPage()
    expect(screen.getByRole('heading', { level: 1, name: 'Análisis IN/OUT' })).toBeInTheDocument()
    expect(screen.getByText('LF Challenge')).toBeInTheDocument()
  })

  it('the two views are tabs: IN/OUT open, the arrow of the keyboard opens IN vs IN', () => {
    renderPage()
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['IN/OUT', 'IN vs IN'])
    expect(screen.getByRole('tab', { name: 'IN/OUT' })).toHaveAttribute('aria-selected', 'true')
    fireEvent.keyDown(screen.getByRole('tab', { name: 'IN/OUT' }), { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'IN vs IN' })).toHaveAttribute('aria-selected', 'true')
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

// Issue #759: IN/OUT had no export. Its results are cards, not a table: the CSV is made of the same figures (statistic, ON, OFF, ON − OFF), the PNG and the PDF capture the results.
const BLOCK = (net: number, ortg: number) => ({ points_for: 105.4, points_against: 98, minutes: 320, net_rating: net, offensive_rating: ortg, defensive_rating: 102.7 })
const ANALYSIS = (id: string, name: string, on: number, off: number) => ({ player_id: id, player_name: name, team_name: 'Alfa', on: BLOCK(on, 110.2), off: BLOCK(off, 98) })
const PLAYERS = [
  { player_id: '7', player_name: 'A. JUGADORA', team_name: 'Alfa', team_id: '1', games_played: 5 },
  { player_id: '8', player_name: 'B. JUGADORA', team_name: 'Alfa', team_id: '1', games_played: 5 },
]

describe('InOutPage export (issue #759)', () => {
  beforeEach(() => {
    api.getPlayerStats.mockResolvedValue(PLAYERS)
    api.getInOutAnalysis.mockImplementation(async (_c: string, id: string) => (id === '7' ? ANALYSIS('7', 'A. JUGADORA', 7.5, -2) : ANALYSIS('8', 'B. JUGADORA', 1.5, 0)))
  })

  it('offers CSV, PNG and PDF once a player is analysed, and nothing before', async () => {
    renderPage()
    await screen.findByRole('option', { name: /A\. JUGADORA/ })
    expect(screen.queryByRole('button', { name: /Exportar/ })).toBeNull()
    fireEvent.change(screen.getByLabelText('Jugador'), { target: { value: '7' } })
    fireEvent.click(await screen.findByRole('button', { name: /Exportar/ }))
    expect(['CSV', 'PNG', 'PDF'].every(name => screen.getByRole('button', { name })) ).toBe(true)
  })

  it('the CSV has the statistic, ON, OFF and the difference of the player analysed', async () => {
    const blobs = captureDownloads()
    renderPage()
    await screen.findByRole('option', { name: /A\. JUGADORA/ })
    fireEvent.change(screen.getByLabelText('Jugador'), { target: { value: '7' } })
    fireEvent.click(await screen.findByRole('button', { name: /Exportar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'CSV' }))
    const lines = (await blobs[0].text()).split('\n')
    expect(lines[0]).toBe('"Estadística","ON","OFF","ON − OFF"')
    expect(lines).toContain('Net Rating,7.5,-2,9.5')
  })

  it('in IN vs IN it exports the ON of the two players and their difference once both are chosen', async () => {
    const blobs = captureDownloads()
    renderPage()
    await screen.findByRole('option', { name: /A\. JUGADORA/ })
    fireEvent.keyDown(screen.getByRole('tab', { name: 'IN/OUT' }), { key: 'ArrowRight' })
    fireEvent.change(screen.getByLabelText('Jugador 1'), { target: { value: '7' } })
    expect(screen.queryByRole('button', { name: /Exportar/ })).toBeNull()                 // with one player only there is nothing to compare
    fireEvent.change(screen.getByLabelText('Jugador 2'), { target: { value: '8' } })
    fireEvent.click(await screen.findByRole('button', { name: /Exportar/ }))
    fireEvent.click(screen.getByRole('button', { name: 'CSV' }))
    const lines = (await blobs[0].text()).split('\n')
    expect(lines[0]).toBe('"Estadística","A. JUGADORA (ON)","B. JUGADORA (ON)","Diferencia"')
    expect(lines).toContain('Net Rating,7.5,1.5,6')
  })
})
