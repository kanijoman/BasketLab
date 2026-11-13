import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import MarketApp from './MarketApp'
import { resetTalentData, setTalentBase } from './data'
import { serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

beforeEach(() => { resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData().override['index.json'] = null })        // nothing published

const at = (path: string) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><MarketApp /></MemoryRouter></QueryClientProvider>)

describe('BasketLab Talent (shell, #877)', () => {
  it('opens on the search and says there is no data published yet', async () => {
    at('/')
    expect(await screen.findByRole('heading', { level: 1, name: /Buscador de jugadores/ })).toBeInTheDocument()
    expect(await screen.findByText(/Aún no hay datos de jugadores publicados/)).toBeInTheDocument()
  })

  it('sends any other address to the search instead of an empty page', async () => {
    at('/no-existe/de/verdad')
    expect(await screen.findByRole('heading', { level: 1, name: /Buscador de jugadores/ })).toBeInTheDocument()
  })

  it('has a skip link and a main landmark like the rest of the suite (keyboard and screen readers)', () => {
    at('/')
    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Saltar al contenido/i })).toHaveAttribute('href', '#contenido')
  })

  it('shows the mark of Talent (ball and lens) in the header, not the trend mark of Analytics (#901)', () => {
    const { container } = at('/')
    const src = container.querySelector('header img')?.getAttribute('src') ?? ''
    const svg = src.startsWith('data:image/svg+xml;base64,') ? atob(src.split(',')[1]) : src         // Vite inlines small SVGs
    expect(svg).toContain('data-part="lens"')
    expect(svg).not.toContain('M 8 70 L 32 58 L 48 64 L 80 34')
  })
})
