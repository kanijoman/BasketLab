import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import MarketApp from './MarketApp'

const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><MarketApp /></MemoryRouter>)

describe('BasketLab Talent (shell, #877)', () => {
  it('opens on the home with the name of the product and says there is no data published yet', () => {
    at('/')
    expect(screen.getByRole('heading', { level: 1, name: /BasketLab Talent/ })).toBeInTheDocument()
    expect(screen.getByText(/Aún no hay datos de jugadores publicados/)).toBeInTheDocument()
  })

  it('sends any other address to the home instead of an empty page', () => {
    at('/no-existe/de/verdad')
    expect(screen.getByRole('heading', { level: 1, name: /BasketLab Talent/ })).toBeInTheDocument()
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
