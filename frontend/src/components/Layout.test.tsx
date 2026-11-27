import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Layout from './Layout'
import * as client from '@/api/client'
import * as webdata from '@/webdata/client'
import { BASE_SECTIONS } from '@/test/sections'

const phone = (matches: boolean) => vi.stubGlobal('matchMedia', (query: string) => ({
  matches: matches && query.includes('max-width'), media: query, addEventListener: () => undefined, removeEventListener: () => undefined }))

function shell(path: string) {
  vi.spyOn(client, 'getCollectionList').mockResolvedValue([])
  vi.spyOn(webdata, 'publishedSectionsOf').mockResolvedValue(new Set(BASE_SECTIONS))          // the menu offers the pages whose section is published (#1100)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route element={<Layout />}>
          <Route path="/" element={<p>Portada</p>} />
          <Route path="/:collection/*" element={<p>Página</p>} />
        </Route></Routes>
      </MemoryRouter>
    </QueryClientProvider>)
}

beforeEach(() => localStorage.clear())
afterEach(() => { phone(false); vi.restoreAllMocks() })            // not unstubAllGlobals: it would also drop the in-memory localStorage of the setup

// Issue #191 (U4): the shell on a phone has no fixed sidebar: a menu button opens it over the page.
describe('Layout shell (issue #191)', () => {
  it('on a wide screen the sidebar is there and there is no menu button', () => {
    phone(false)
    shell('/LF2/teams')
    expect(screen.getByRole('navigation', { name: 'Páginas de la competición' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Abrir menú' })).toBeNull()
  })

  it('on a phone the page has the whole width: a menu button opens the navigation and choosing a page closes it', async () => {
    phone(true)
    shell('/LF2/teams')
    expect(screen.queryByRole('navigation', { name: 'Páginas de la competición' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir menú' }))
    const dialog = screen.getByRole('dialog', { name: 'Menú de navegación' })
    fireEvent.click(await within(dialog).findByRole('link', { name: 'Rankings' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  // Issue #197 (U7): the keyboard reaches the page without crossing the whole menu
  it('has a first link that skips the navigation to the content of the page', () => {
    phone(false)
    shell('/LF2/teams')
    const skip = screen.getByRole('link', { name: 'Saltar al contenido' })
    expect(skip).toHaveAttribute('href', '#contenido')
    expect(document.querySelector('main#contenido')).not.toBeNull()
    expect(document.body.querySelector('a, button')).toBe(skip)                       // the first thing the Tab key finds
  })

  // Issue #666 (U5e): going home is a link (it goes to a page), not a button that navigates
  it('in a competition the breadcrumb has a link home', () => {
    phone(false)
    shell('/LF2/teams')
    expect(within(screen.getByRole('navigation', { name: 'Ruta' })).getByRole('link', { name: 'Inicio' })).toHaveAttribute('href', '/')
  })

  it('outside a competition there is no navigation to open', () => {
    phone(true)
    shell('/')
    expect(screen.queryByRole('button', { name: 'Abrir menú' })).toBeNull()
  })
})

// Issues #327, #334: the header says when something comes from the API (the default is the published files), so a table from the API is not taken for a local one.
// #884 (PR C): the notice of a stale external source sits under the header, above every page of an external competition, and only there.
describe('Layout notice of a stale external source (#884)', () => {
  const failed = { source: 'ncaa', state: 'failed', ok: false, last_ok: '2026-11-17T07:00:00Z', finished: '2026-11-18T07:00:00Z', games: 13, unreliable: 12, published: 1 } as const

  it('shows it above the page of an external competition whose source failed', async () => {
    vi.spyOn(webdata, 'loadSourceFreshness').mockResolvedValue([failed])
    shell('/NCAA_D1_2026_SEC/teams')
    const notice = await screen.findByRole('status')
    expect(notice).toHaveTextContent('Datos de NCAA del 17/11: la última actualización falló.')
    expect(notice.compareDocumentPosition(screen.getByText('Página')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()      // before the page, not after
  })

  it('does not show it on a competition of FEB, nor ask for it', async () => {
    const asked = vi.spyOn(webdata, 'loadSourceFreshness').mockResolvedValue([failed])
    shell('/LF2/teams')
    await screen.findByText('Página')
    expect(screen.queryByRole('status')).toBeNull()
    expect(asked).not.toHaveBeenCalled()
  })
})

