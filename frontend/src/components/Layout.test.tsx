import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Layout from './Layout'
import * as client from '@/api/client'

const phone = (matches: boolean) => vi.stubGlobal('matchMedia', (query: string) => ({
  matches: matches && query.includes('max-width'), media: query, addEventListener: () => undefined, removeEventListener: () => undefined }))

function shell(path: string) {
  vi.spyOn(client, 'getCollectionList').mockResolvedValue([])
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

  it('on a phone the page has the whole width: a menu button opens the navigation and choosing a page closes it', () => {
    phone(true)
    shell('/LF2/teams')
    expect(screen.queryByRole('navigation', { name: 'Páginas de la competición' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir menú' }))
    const dialog = screen.getByRole('dialog', { name: 'Menú de navegación' })
    fireEvent.click(within(dialog).getByRole('link', { name: 'Rankings' }))
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
describe('Layout API data tag (issues #327, #334)', () => {
  it('shows nothing by default (everything is local) and «Datos de la API» when the API is forced', () => {
    phone(false)
    shell('/LF2/teams')
    expect(screen.queryByText('Datos de la API')).toBeNull()
    expect(screen.queryByText('Datos locales')).toBeNull()
    cleanup()
    localStorage.setItem('basketlab.data', 'api')
    shell('/LF2/teams')
    expect(screen.getByText('Datos de la API')).toBeInTheDocument()
  })

  // Issue #329: with only some datasets local, the tag says which ones still read the API.
  it('says which datasets still read the API when only some are local', () => {
    phone(false)
    localStorage.setItem('basketlab.data', 'local:team-report')
    shell('/LF2/team-report')
    const title = screen.getByText('Datos de la API').getAttribute('title') ?? ''
    expect(title).toContain('team-stats')
    expect(title).not.toContain('team-report,')
  })
})
