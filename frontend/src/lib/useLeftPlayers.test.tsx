import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DATA_FLAG_KEY } from '@/datasource/switch'

const web = vi.hoisted(() => ({ loadWebImages: vi.fn() }))
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), ...web }))

import { useLeftPlayers } from './useLeftPlayers'

// #1082: the players of a team whose line of the FEB has a baja already reached are left out of the lists by team.
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>
)
const person = (baja?: string | null) => ({ name: null, no: null, photo: null, birth_date: null, height: null, baja })
const COLLECTION = 'PRIMERA_FEB_2026_2027_Liga_Regular_Unico'

beforeEach(() => { localStorage.clear(); localStorage.setItem(DATA_FLAG_KEY, 'local'); web.loadWebImages.mockReset() })
afterEach(() => localStorage.clear())

describe('useLeftPlayers', () => {
  it('is the ids of the players with a baja already reached, and not those without it or with one still to come', async () => {
    web.loadWebImages.mockResolvedValue({ players: { '1': person('2026-01-10'), '2': person(null), '3': person('2999-01-01'), '4': person() } })
    const { result } = renderHook(() => useLeftPlayers(COLLECTION, '101'), { wrapper })
    await waitFor(() => expect(result.current.size).toBe(1))
    expect([...result.current]).toEqual(['1'])
    expect(web.loadWebImages).toHaveBeenCalledWith(COLLECTION, '101')
  })

  it.each([
    ['no team chosen', COLLECTION, ''],
    ['no competition', undefined, '101'],
    ['FBCYL, which has no such table', 'FBCYL_1ª_AA_FASE-GRUPO_A-1_2026', '34001'],
  ])('asks nothing and hides nobody: %s', (_name, collection, team) => {
    const { result } = renderHook(() => useLeftPlayers(collection, team), { wrapper })
    expect(result.current.size).toBe(0)
    expect(web.loadWebImages).not.toHaveBeenCalled()
  })

  it('asks nothing when the web data is off (the API is the source)', () => {
    localStorage.setItem(DATA_FLAG_KEY, 'api')
    renderHook(() => useLeftPlayers(COLLECTION, '101'), { wrapper })
    expect(web.loadWebImages).not.toHaveBeenCalled()
  })

  it('never hides anybody for not knowing: a publication that cannot be read or has no key leaves everybody in', async () => {
    web.loadWebImages.mockRejectedValue(new Error('sin clave'))
    const { result } = renderHook(() => useLeftPlayers(COLLECTION, '101'), { wrapper })
    await waitFor(() => expect(web.loadWebImages).toHaveBeenCalled())
    expect(result.current.size).toBe(0)
  })
})
