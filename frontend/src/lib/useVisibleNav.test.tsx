import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const published = vi.hoisted(() => ({ publishedSectionsOf: vi.fn() }))
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), ...published }))

import { useVisibleNavGroups } from './useVisibleNav'
import { NAV_ITEMS } from './nav'

// Issue #780: a page that depends on a section of web-data is hidden while the competition does not have it published (no «próximamente»).
const subPaths = (groups: ReturnType<typeof useVisibleNavGroups>) => groups.flatMap(g => g.items.map(i => i.subPath))

beforeEach(() => {
  localStorage.clear()
  published.publishedSectionsOf.mockReset().mockResolvedValue(new Set(['rows']))
})

describe('useVisibleNavGroups', () => {
  it('hides Conexiones while the competition has not the section published, and keeps every other page', async () => {
    const { result } = renderHook(() => useVisibleNavGroups('LF2'))
    await waitFor(() => expect(published.publishedSectionsOf).toHaveBeenCalledWith('LF2'))
    expect(subPaths(result.current)).not.toContain('conexiones')
    expect(subPaths(result.current)).toHaveLength(NAV_ITEMS.length - 2)                      // - Conexiones - the summary, which is not in a group
  })

  it('shows it as soon as the publication has the section for that competition', async () => {
    published.publishedSectionsOf.mockResolvedValue(new Set(['rows', 'assist_connections']))
    const { result } = renderHook(() => useVisibleNavGroups('LF2'))
    await waitFor(() => expect(subPaths(result.current)).toContain('conexiones'))
  })

  it('does not show it while the publication is still being read (no flicker)', () => {
    published.publishedSectionsOf.mockReturnValue(new Promise(() => undefined))
    const { result } = renderHook(() => useVisibleNavGroups('LF2'))
    expect(subPaths(result.current)).not.toContain('conexiones')
  })

  it('with the API as the source (?data=api, development) every page is offered: nothing to wait for', () => {
    localStorage.setItem('basketlab.data', 'api')
    const { result } = renderHook(() => useVisibleNavGroups('LF2'))
    expect(subPaths(result.current)).toContain('conexiones')
    expect(published.publishedSectionsOf).not.toHaveBeenCalled()
  })

  it('a publication that cannot be read hides the page instead of breaking the menu', async () => {
    published.publishedSectionsOf.mockRejectedValue(new Error('down'))
    const { result } = renderHook(() => useVisibleNavGroups('LF2'))
    await waitFor(() => expect(published.publishedSectionsOf).toHaveBeenCalled())
    expect(subPaths(result.current)).not.toContain('conexiones')
  })

  it('asks again when the competition changes: a section is per competition', async () => {
    published.publishedSectionsOf.mockImplementation(async (c: string) => new Set(c === 'LF2' ? ['assist_connections'] : []))
    const { result, rerender } = renderHook(({ c }) => useVisibleNavGroups(c), { initialProps: { c: 'LF2' } })
    await waitFor(() => expect(subPaths(result.current)).toContain('conexiones'))
    rerender({ c: 'OTHER' })
    await waitFor(() => expect(subPaths(result.current)).not.toContain('conexiones'))
  })
})
