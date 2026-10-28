import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
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

  it('outside a competition there is no navigation to open', () => {
    phone(true)
    shell('/')
    expect(screen.queryByRole('button', { name: 'Abrir menú' })).toBeNull()
  })
})
