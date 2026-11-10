import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getTeamStats: vi.fn() }))
vi.mock('@/api/client', async importOriginal => ({ ...(await importOriginal<object>()), ...api }))

import { useTeamOptions } from './useTeamOptions'

// Issue #452: LineupsPage, RotacionesPage, ConexionesPage and InOutPage each built the same {id, name} list of the teams of a collection.
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
)
const stats = (rows: Array<{ team_name: string; team_id?: number | null }>) => ({ team_stats: rows })

beforeEach(() => api.getTeamStats.mockReset())

describe('useTeamOptions', () => {
  it('lists the teams by name, with the id as a string and the name as the id when the team has none', async () => {
    api.getTeamStats.mockResolvedValue(stats([{ team_name: 'Zeta', team_id: 7 }, { team_name: 'Álamo' }, { team_name: 'Beta', team_id: null }]))
    const { result } = renderHook(() => useTeamOptions('LF2'), { wrapper })
    await waitFor(() => expect(result.current).toHaveLength(3))
    expect(result.current).toEqual([{ id: 'Álamo', name: 'Álamo' }, { id: 'Beta', name: 'Beta' }, { id: '7', name: 'Zeta' }])
  })

  it('can keep only the teams with an id (the IN/OUT page matches players by it)', async () => {
    api.getTeamStats.mockResolvedValue(stats([{ team_name: 'Zeta', team_id: 7 }, { team_name: 'Álamo' }]))
    const { result } = renderHook(() => useTeamOptions('LF2', { onlyWithId: true }), { wrapper })
    await waitFor(() => expect(result.current).toHaveLength(1))
    expect(result.current).toEqual([{ id: '7', name: 'Zeta' }])
  })

  it('is empty, and asks nothing, without a collection', () => {
    const { result } = renderHook(() => useTeamOptions(undefined), { wrapper })
    expect(result.current).toEqual([])
    expect(api.getTeamStats).not.toHaveBeenCalled()
  })
})
