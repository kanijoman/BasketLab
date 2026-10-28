import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CollectionSwitcher from './CollectionSwitcher'
import * as client from '@/api/client'

const LIST = [
  { name: 'LF2_2025_A', league: 'FEB', competition: 'LF2', season: '2025-2026', group: 'A', game_count: 30 },
  { name: 'LF2_2025_B', league: 'FEB', competition: 'LF2', season: '2025-2026', group: 'B', game_count: 28 },
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
  it('lists the competitions with the current one chosen', async () => {
    show('/LF2_2025_A/teams')
    const select = await screen.findByRole('combobox', { name: 'Competición' })
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(2))
    expect(select).toHaveValue('LF2_2025_A')
  })

  it('goes to the same page of the other competition', async () => {
    show('/LF2_2025_A/lineups')
    fireEvent.change(await screen.findByRole('combobox', { name: 'Competición' }), { target: { value: 'LF2_2025_B' } })
    expect(screen.getByTestId('where')).toHaveTextContent('/LF2_2025_B/lineups')
  })

  it('from the summary it goes to the summary', async () => {
    show('/LF2_2025_A')
    fireEvent.change(await screen.findByRole('combobox', { name: 'Competición' }), { target: { value: 'LF2_2025_B' } })
    expect(screen.getByTestId('where')).toHaveTextContent('/LF2_2025_B')
  })

  it('with a single competition there is nothing to choose: it renders nothing', async () => {
    show('/LF2_2025_A', LIST.slice(0, 1))
    await waitFor(() => expect(client.getCollectionList).toHaveBeenCalled())
    expect(screen.queryByRole('combobox')).toBeNull()
  })
})
