import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CollectionSwitcher from './CollectionSwitcher'
import * as client from '@/api/client'

const LIST = [
  { name: 'LF2_2025_A', league: 'FEB', competition: 'LF2', season: '2025_2026', group: 'A', game_count: 30 },
  { name: 'LF2_2025_B', league: 'FEB', competition: 'LF2', season: '2025_2026', group: 'B', game_count: 28 },
] as client.CollectionInfo[]

function Where() { return <p data-testid="where">{useLocation().pathname}</p> }

function show(path: string, list = LIST) {
  vi.spyOn(client, 'getCollectionList').mockResolvedValue(list)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/:collection/*" element={<><CollectionSwitcher /><Where /></>} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>)
}

afterEach(() => vi.restoreAllMocks())

// Issue #191 (U4): change of competition from the header, staying on the same page.
describe('CollectionSwitcher (issue #191)', () => {
  it('shows the same selectors whatever the data: ámbito, categoría, temporada, competición and grupo, starting on the current competition (#761, #912)', async () => {
    show('/LF2_2025_A/teams')
    const select = await screen.findByRole('combobox', { name: 'Grupo' })
    expect(select).toHaveValue('A')
    expect(screen.getAllByRole('combobox').map(s => s.getAttribute('aria-label'))).toEqual(['Ámbito', 'Categoría', 'Temporada', 'Competición', 'Grupo'])      // one ámbito, one season, one competition: still selectors
  })

  it('FBCYL shows the same selectors as FEB even with one season and one competition: the header does not change when you choose it (#912)', async () => {
    const both = [
      ...LIST,
      { name: 'FBCYL_1ª_2026_FASE-GRUPO_A-1', league: 'FBCYL', competition: '1ª', season: '2026 FASE-GRUPO A-1', group: '', game_count: 20 },
      { name: 'FBCYL_1ª_2026_FASE-GRUPO_A-2', league: 'FBCYL', competition: '1ª', season: '2026 FASE-GRUPO A-2', group: '', game_count: 20 },
    ] as client.CollectionInfo[]
    show('/LF2_2025_A/teams', both)
    const feb = (await screen.findAllByRole('combobox')).map(s => s.getAttribute('aria-label'))
    cleanup()
    show('/FBCYL_1ª_2026_FASE-GRUPO_A-1/teams', both)
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Ámbito' })).toHaveValue('FBCYL'))
    expect(screen.getAllByRole('combobox').map(s => s.getAttribute('aria-label'))).toEqual(feb)
    expect(screen.getByRole('combobox', { name: 'Temporada' })).toHaveValue('2026/2027')
    expect(screen.getByRole('combobox', { name: 'Competición' })).toHaveValue('1ª División Femenina')
  })

  it('the header shows the group too when it is the only one: it names the phase', async () => {
    const two = [
      { name: 'PRIMERA_FEB_2026_2027_Liga_Regular_Único', league: 'FEB', competition: 'PRIMERA_FEB', season: '2026_2027_Liga_Regular_Único', group: '', game_count: 40 },
      { name: 'LF_ENDESA_2026_2027_Liga_Regular_Único', league: 'FEB', competition: 'LF_ENDESA', season: '2026_2027_Liga_Regular_Único', group: '', game_count: 30 },
    ] as client.CollectionInfo[]
    show('/PRIMERA_FEB_2026_2027_Liga_Regular_Único/teams', two)
    expect(await screen.findByRole('combobox', { name: 'Grupo' })).toHaveValue('Liga Regular')
    expect(screen.getByRole('combobox', { name: 'Competición' })).toHaveValue('PRIMERA FEB')
    expect(screen.getByRole('combobox', { name: 'Temporada' })).toHaveValue('2026/2027')            // one season: still a selector (#912)
  })

  it('changing the season keeps the page and the competition when they exist there (#761)', async () => {
    show('/LF2_2025_A/rotaciones', [...LIST, { ...LIST[0], name: 'LF2_2024_A', season: '2024_2025' }] as client.CollectionInfo[])
    fireEvent.change(await screen.findByRole('combobox', { name: 'Temporada' }), { target: { value: '2024/2025' } })
    expect(screen.getByTestId('where')).toHaveTextContent('/LF2_2024_A/rotaciones')
  })

  it('goes to the same page of the other competition', async () => {
    show('/LF2_2025_A/lineups')
    fireEvent.change(await screen.findByRole('combobox', { name: 'Grupo' }), { target: { value: 'B' } })
    expect(screen.getByTestId('where')).toHaveTextContent('/LF2_2025_B/lineups')
  })

  it('from the summary it goes to the summary', async () => {
    show('/LF2_2025_A')
    fireEvent.change(await screen.findByRole('combobox', { name: 'Grupo' }), { target: { value: 'B' } })
    expect(screen.getByTestId('where')).toHaveTextContent('/LF2_2025_B')
  })

  it('with a single competition there is nothing to choose: it renders nothing', async () => {
    show('/LF2_2025_A', LIST.slice(0, 1))
    await waitFor(() => expect(client.getCollectionList).toHaveBeenCalled())
    expect(screen.queryByRole('combobox')).toBeNull()
  })
})
