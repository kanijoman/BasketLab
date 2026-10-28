import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Sidebar, { MobileNav } from './Sidebar'
import { NAV_ITEMS } from '@/lib/nav'

const at = (path: string, ui: React.ReactNode) => render(
  <MemoryRouter initialEntries={[path]}><Routes><Route path="/:collection/*" element={ui} /></Routes></MemoryRouter>)

beforeEach(() => localStorage.clear())

// Issue #191 (U4): the navigation is grouped; on a phone it is a menu that opens over the page.
describe('Sidebar (issue #191)', () => {
  it('groups the pages under their heading and points every link at its page', () => {
    at('/LF2/teams', <Sidebar />)
    const nav = screen.getByRole('navigation', { name: 'Páginas de la competición' })
    for (const group of ['Equipos', 'Jugadores', 'Partido', 'Live', 'Informes']) {
      expect(within(nav).getByRole('heading', { name: group })).toBeInTheDocument()
    }
    expect(within(nav).getAllByRole('link')).toHaveLength(NAV_ITEMS.length + 1)           // + Administración
    expect(within(nav).getByRole('link', { name: 'Equipo' })).toHaveAttribute('href', '/LF2/teams')
    expect(within(nav).getByRole('link', { name: 'Resumen' })).toHaveAttribute('href', '/LF2')
    expect(within(nav).getByRole('link', { name: 'Equipo' })).toHaveAttribute('aria-current', 'page')
  })

  it('collapsed it shows the icons only, with the names as titles, and remembers it', () => {
    at('/LF2', <Sidebar />)
    fireEvent.click(screen.getByRole('button', { name: 'Colapsar menú' }))
    expect(screen.queryByRole('heading', { name: 'Equipos' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Equipo' })).toHaveAttribute('title', 'Equipo')
    expect(localStorage.getItem('sidebar-collapsed')).toBe('true')
  })
})

describe('MobileNav (issue #191)', () => {
  function Menu({ open = true, onClose = () => undefined }: { open?: boolean; onClose?: () => void }) {
    return <MobileNav open={open} onClose={onClose} />
  }

  it('is a modal dialog with the same grouped links', () => {
    at('/LF2/players', <Menu />)
    const dialog = screen.getByRole('dialog', { name: 'Menú de navegación' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByRole('heading', { name: 'Jugadores' })).toBeInTheDocument()
    expect(within(dialog).getByRole('link', { name: 'Individual' })).toHaveAttribute('aria-current', 'page')
  })

  it('is not in the page while it is closed', () => {
    at('/LF2', <Menu open={false} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('closes with Escape, with the backdrop, with its button and when a page is chosen', () => {
    const close = vi.fn()
    at('/LF2', <Menu onClose={close} />)
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByTestId('nav-backdrop'))
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar menú' }))
    fireEvent.click(screen.getByRole('link', { name: 'Rankings' }))
    expect(close).toHaveBeenCalledTimes(4)
  })

  it('puts the focus inside when it opens', () => {
    at('/LF2', <Menu />)
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement)
  })
})
