import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Tooltip, { tippedHeader } from './Tooltip'

// -- Tooltip component ---------------------------------------------------------

describe('Tooltip - renders children and portal bubble on hover', () => {
  it('renders children by default', () => {
    render(<Tooltip text="Test tooltip">Hover me</Tooltip>)
    expect(screen.getByText('Hover me')).toBeInTheDocument()
  })

  it('tooltip is NOT in DOM before hover (portal-based)', () => {
    render(<Tooltip text="Stat description">PPP</Tooltip>)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('tooltip appears in DOM after mouseEnter', async () => {
    const user = userEvent.setup()
    render(<Tooltip text="hover tooltip">target</Tooltip>)
    const trigger = screen.getByText('target')
    await user.hover(trigger)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(screen.getByRole('tooltip')).toHaveTextContent('hover tooltip')
  })

  it('tooltip disappears after mouseLeave', async () => {
    const user = userEvent.setup()
    render(<Tooltip text="bye tooltip">target</Tooltip>)
    const trigger = screen.getByText('target')
    await user.hover(trigger)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await user.unhover(trigger)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('forwards className to wrapper span', () => {
    const { container } = render(
      <Tooltip text="Test" className="custom-class">child</Tooltip>,
    )
    expect(container.firstChild).toHaveClass('custom-class')
  })
})

// -- tippedHeader helper -------------------------------------------------------

describe('tippedHeader - returns known abbreviations with tooltip', () => {
  it('returns the raw string for unknown abbreviations', () => {
    const result = tippedHeader('UNKNOWN_ABBR')
    expect(result).toBe('UNKNOWN_ABBR')
  })

  it('returns a function (not a string) for known abbreviations', () => {
    const result = tippedHeader('PPP')
    expect(typeof result).toBe('function')
  })

  it('renders the abbreviation text for PPP', () => {
    const fn = tippedHeader('PPP') as () => JSX.Element
    render(<>{fn()}</>)
    expect(screen.getByText('PPP')).toBeInTheDocument()
  })

  it('shows tooltip with label on hover for PPP', async () => {
    const user = userEvent.setup()
    const fn = tippedHeader('PPP') as () => JSX.Element
    render(<>{fn()}</>)
    await user.hover(screen.getByText('PPP'))
    expect(screen.getByRole('tooltip').textContent).toContain('Puntos Por Partido')
  })

  it('shows tooltip on hover for advanced stat OER', async () => {
    const user = userEvent.setup()
    const fn = tippedHeader('OER') as () => JSX.Element
    render(<>{fn()}</>)
    await user.hover(screen.getByText('OER'))
    expect(screen.getByRole('tooltip').textContent).toContain('100')
  })

  it('shows tooltip for eFG%', async () => {
    const user = userEvent.setup()
    const fn = tippedHeader('eFG%') as () => JSX.Element
    render(<>{fn()}</>)
    await user.hover(screen.getByText('eFG%'))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('shows "Menor es mejor" in TOV% tooltip', async () => {
    const user = userEvent.setup()
    const fn = tippedHeader('TOV%') as () => JSX.Element
    render(<>{fn()}</>)
    await user.hover(screen.getByText('TOV%'))
    expect(screen.getByRole('tooltip').textContent).toContain('Menor es mejor')
  })

  it('renders DER abbreviation', () => {
    const fn = tippedHeader('DER') as () => JSX.Element
    render(<>{fn()}</>)
    expect(screen.getByText('DER')).toBeInTheDocument()
  })

  it('applies dotted underline decoration to abbreviation span', () => {
    const fn = tippedHeader('PPP') as () => JSX.Element
    const { container } = render(<>{fn()}</>)
    const span = container.querySelector('.underline.decoration-dotted')
    expect(span).not.toBeNull()
    expect(span?.textContent).toBe('PPP')
  })
})

