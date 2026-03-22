import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import TrendBadge from './TrendBadge'

function renderBadge(recent: number | null, season: number | null, reverse = false) {
  return render(<TrendBadge recent={recent} season={season} reverse={reverse} />)
}

describe('TrendBadge — threshold arrows', () => {
  it('shows ⇈ when improvement > 10%', () => {
    renderBadge(112, 100)
    expect(screen.getByText('⇈')).toBeInTheDocument()
  })

  it('shows ↑ when improvement 5–10%', () => {
    renderBadge(107, 100)
    expect(screen.getByText('↑')).toBeInTheDocument()
  })

  it('shows ≈ when change < 5%', () => {
    renderBadge(102, 100)
    expect(screen.getByText('≈')).toBeInTheDocument()
  })

  it('shows ↓ when decline 5–10%', () => {
    renderBadge(93, 100)
    expect(screen.getByText('↓')).toBeInTheDocument()
  })

  it('shows ⇊ when decline > 10%', () => {
    renderBadge(88, 100)
    expect(screen.getByText('⇊')).toBeInTheDocument()
  })
})

describe('TrendBadge — reverse mode (lower is better)', () => {
  it('shows ⇈ when value drops > 10% and reverse=true', () => {
    renderBadge(88, 100, true)
    expect(screen.getByText('⇈')).toBeInTheDocument()
  })

  it('shows ⇊ when value rises > 10% and reverse=true', () => {
    renderBadge(112, 100, true)
    expect(screen.getByText('⇊')).toBeInTheDocument()
  })
})

describe('TrendBadge — null safety', () => {
  it('renders nothing when season is null', () => {
    const { container } = renderBadge(100, null)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when recent is null', () => {
    const { container } = renderBadge(null, 100)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when season is 0 (avoid division by zero)', () => {
    const { container } = renderBadge(100, 0)
    expect(container).toBeEmptyDOMElement()
  })
})
