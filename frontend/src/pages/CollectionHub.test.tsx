import { render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CollectionHub from './CollectionHub'
import { CollectionProvider } from '@/context/CollectionContext'
import * as client from '@/api/client'
import { NAV_GROUPS } from '@/lib/nav'

function hub() {
  vi.spyOn(client, 'getTeamStats').mockResolvedValue({ team_stats: [], opponent_stats: [] } as never)
  vi.spyOn(client, 'getPlayerStats').mockResolvedValue([] as never)
  render(
    <MemoryRouter initialEntries={['/LF2_2025_A']}>
      <Routes><Route path="/:collection" element={<CollectionProvider><CollectionHub /></CollectionProvider>} /></Routes>
    </MemoryRouter>)
}

afterEach(() => vi.restoreAllMocks())

// Issue #191 (U4): the summary of a competition is the cards of EVERY page, in the groups of the menu, each one a link.
describe('CollectionHub (issue #191)', () => {
  it('has a group per heading of the menu with a card for each of its pages, all of them links', async () => {
    hub()
    await screen.findByRole('heading', { level: 1 })
    for (const group of NAV_GROUPS) {
      const section = screen.getByRole('region', { name: group.label })
      expect(within(section).getAllByRole('link')).toHaveLength(group.items.length)
      for (const item of group.items) {
        expect(within(section).getByRole('link', { name: new RegExp(item.title ?? item.label) })).toHaveAttribute('href', `/LF2_2025_A/${item.subPath}`)
      }
    }
  })

  it('the pages that had no card (pbp, multifase, partido, rotaciones) have it now', async () => {
    hub()
    await screen.findByRole('heading', { level: 1 })
    for (const page of ['pbp', 'multiphase', 'matches', 'rotaciones']) {
      expect(document.querySelector(`a[href="/LF2_2025_A/${page}"]`), page).not.toBeNull()
    }
  })
})
