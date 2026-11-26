import { render, screen, within } from '@testing-library/react'
import { BASE_SECTIONS } from '@/test/sections'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
const published = vi.hoisted(() => ({ publishedSectionsOf: vi.fn() }))
vi.mock('@/webdata/client', async importOriginal => ({ ...(await importOriginal<object>()), ...published }))

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

beforeEach(() => {
  localStorage.setItem('basketlab.data', 'local')
  published.publishedSectionsOf.mockReset().mockResolvedValue(new Set(BASE_SECTIONS))
})
afterEach(() => vi.restoreAllMocks())

// Issue #191 (U4): the summary of a competition is the cards of EVERY page, in the groups of the menu, each one a link.
describe('CollectionHub (issue #191)', () => {
  it('has a group per heading of the menu with a card for each of its pages, all of them links', async () => {
    hub()
    await screen.findByRole('heading', { level: 1 })
    await screen.findByRole('region', { name: 'Equipos' })                              // the cards appear once the publication has been read (#1100)
    for (const group of NAV_GROUPS) {
      const offered = group.items.filter(item => !item.requires || BASE_SECTIONS.includes(item.requires.section))      // the pages whose section is not published are not offered here (#780, below)
      if (!offered.length) {                                                           // a group whose pages all need one (Competición, #850) has no card until they are published
        expect(screen.queryByRole('region', { name: group.label })).toBeNull()
        continue
      }
      const section = screen.getByRole('region', { name: group.label })
      expect(within(section).getAllByRole('link')).toHaveLength(offered.length)
      for (const item of offered) {
        expect(within(section).getByRole('link', { name: new RegExp(item.title ?? item.label) })).toHaveAttribute('href', `/LF2_2025_A/${item.subPath}`)
      }
    }
  })

  it('the pages that had no card (pbp, multifase, partido, rotaciones) have it now', async () => {
    hub()
    await screen.findByRole('heading', { level: 1 })
    await screen.findByRole('region', { name: 'Equipos' })
    for (const page of ['pbp', 'multiphase', 'matches', 'rotaciones']) {
      expect(document.querySelector(`a[href="/LF2_2025_A/${page}"]`), page).not.toBeNull()
    }
  })
})

// Issue #780: the card of a page that needs a section of the publication appears only when the competition has it.
describe('CollectionHub: pages that need published data (issue #780)', () => {
  it('has no card for Conexiones while the competition has not the section published', async () => {
    hub()
    await screen.findByRole('heading', { level: 1 })
    await vi.waitFor(() => expect(published.publishedSectionsOf).toHaveBeenCalledWith('LF2_2025_A'))
    expect(document.querySelector('a[href="/LF2_2025_A/conexiones"]')).toBeNull()
  })

  it('has it once the publication has the section', async () => {
    published.publishedSectionsOf.mockResolvedValue(new Set([...BASE_SECTIONS, 'assist_connections']))
    hub()
    expect(await screen.findByRole('link', { name: /Conexiones de asistencia/ })).toHaveAttribute('href', '/LF2_2025_A/conexiones')
  })
})
