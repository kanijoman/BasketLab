import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import StatCard from './StatCard'

describe('StatCard — rendering', () => {
  it('displays the label', () => {
    render(<StatCard label="OER Medio" value="107.3" />)
    expect(screen.getByText('OER Medio')).toBeInTheDocument()
  })

  it('displays the value', () => {
    render(<StatCard label="PPP" value="82.5" />)
    expect(screen.getByText('82.5')).toBeInTheDocument()
  })

  it('displays the sub caption when provided', () => {
    render(<StatCard label="X" value="1" sub="últimos 7 días" />)
    expect(screen.getByText('últimos 7 días')).toBeInTheDocument()
  })
})

describe('StatCard — accent classes', () => {
  it('applies green accent border class', () => {
    const { container } = render(<StatCard label="OER" value="107" accent="green" />)
    const card = container.firstChild as HTMLElement
    expect(card.className).toMatch(/border-brand/)
  })

  it('applies blue accent class', () => {
    const { container } = render(<StatCard label="DER" value="102" accent="blue" />)
    const card = container.firstChild as HTMLElement
    expect(card.className).toMatch(/border-accent/)
  })

  it('uses default border when no accent provided', () => {
    const { container } = render(<StatCard label="PPP" value="80" />)
    const card = container.firstChild as HTMLElement
    expect(card.className).toMatch(/border-surface-border/)
  })
})

describe('StatCard — interactivity', () => {
  it('has role=button and is clickable when onClick provided', async () => {
    const handle = vi.fn()
    render(<StatCard label="X" value="1" onClick={handle} />)
    const card = screen.getByRole('button')
    await userEvent.click(card)
    expect(handle).toHaveBeenCalledOnce()
  })

  it('has no role when onClick is not provided', () => {
    render(<StatCard label="X" value="1" />)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
