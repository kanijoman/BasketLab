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

  it('outside a competition there is no navigation to open', () => {
    phone(true)
    shell('/')
    expect(screen.queryByRole('button', { name: 'Abrir menú' })).toBeNull()
  })
})

// Issue #327 (step 2): while the tables come from the local files the header says so, so nobody takes them for the API's.
describe('Layout local data tag (issue #327)', () => {
  it('shows «Datos locales» only when the local data source is on', () => {
    phone(false)
    shell('/LF2/teams')
    expect(screen.queryByText('Datos locales')).toBeNull()
    cleanup()
    localStorage.setItem('basketlab.data', 'local')
    shell('/LF2/teams')
    expect(screen.getByText('Datos locales')).toBeInTheDocument()
  })

  // Issue #329: with only some datasets on, the tag says which, so a table from the API is not taken for a local one.
  it('says which datasets are local when only some are (the others still come from the API)', () => {
    phone(false)
    localStorage.setItem('basketlab.data', 'local:team-report')
    shell('/LF2/team-report')
    expect(screen.getByText('Datos locales')).toHaveAttribute('title', expect.stringContaining('team-report'))
    expect(screen.getByText('Datos locales').getAttribute('title')).not.toContain('team-stats')
  })
})
