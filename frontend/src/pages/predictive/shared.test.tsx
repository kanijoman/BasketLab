import { render, renderHook, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getHistoricalSeasons: vi.fn(), getHistoricalTeams: vi.fn() }))
vi.mock('@/api/client', async importOriginal => ({ ...(await importOriginal<object>()), ...api }))

import { HistoricalFields, useHistoricalPicker } from './shared'

// Issue #452: GamePredictionTab and ValidationTab loaded the seasons and the teams by hand, with the same two effects and the same two selects.
beforeEach(() => {
  api.getHistoricalSeasons.mockReset().mockResolvedValue(['2025-26', '2024-25'])
  api.getHistoricalTeams.mockReset().mockImplementation(async (s: string) => (s === '2025-26' ? [{ team_id: 'a', team_name: 'Alfa' }] : [{ team_id: 'b', team_name: 'Beta' }]))
})

describe('useHistoricalPicker', () => {
  it('selects the first season, then the first team of that season', async () => {
    const { result } = renderHook(() => useHistoricalPicker())
    await waitFor(() => expect(result.current.teamId).toBe('a'))
    expect(result.current.season).toBe('2025-26')
    expect(result.current.seasons).toEqual(['2025-26', '2024-25'])
    expect(api.getHistoricalTeams).toHaveBeenCalledWith('2025-26')
  })

  it('reloads the teams, and picks the first of them, when the season changes', async () => {
    const { result, rerender } = renderHook(() => useHistoricalPicker())
    await waitFor(() => expect(result.current.teamId).toBe('a'))
    result.current.setSeason('2024-25')
    rerender()
    await waitFor(() => expect(result.current.teamId).toBe('b'))
    expect(result.current.teams).toEqual([{ team_id: 'b', team_name: 'Beta' }])
  })

  it('stays empty, without failing, when the seasons cannot be read', async () => {
    api.getHistoricalSeasons.mockRejectedValue(new Error('down'))
    const { result } = renderHook(() => useHistoricalPicker())
    await new Promise(r => setTimeout(r, 0))
    expect(result.current.seasons).toEqual([])
    expect(result.current.teamId).toBe('')
  })
})

describe('HistoricalFields', () => {
  it('shows the season and the team selects', async () => {
    const Probe = () => <HistoricalFields picker={useHistoricalPicker()} />
    render(<Probe />)
    await waitFor(() => expect(screen.getByText('Alfa')).toBeInTheDocument())
    expect(screen.getByText('Temporada')).toBeInTheDocument()
    expect(screen.getByText('Equipo')).toBeInTheDocument()
  })
})
