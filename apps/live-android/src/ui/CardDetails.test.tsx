import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CardDetails from './CardDetails'

describe('CardDetails (issue #484, feedback of 0.3.2)', () => {
  it('is a chevron, not the words «Ver detalle»; the name is for who cannot see it', () => {
    const { container } = render(<CardDetails><p>Dentro</p></CardDetails>)
    const summary = container.querySelector('summary') as HTMLElement
    expect(summary.textContent?.trim()).toBe('')                       // no visible text: an arrow
    expect(summary.querySelector('svg')).toBeTruthy()
    expect(screen.getByLabelText('Ver detalle')).toBe(summary)
  })

  it('starts closed with the content hidden, and the chevron says so', () => {
    const { container } = render(<CardDetails><p>Dentro</p></CardDetails>)
    expect((container.querySelector('details') as HTMLDetailsElement).open).toBe(false)
    expect(container.querySelector('summary')?.getAttribute('aria-expanded')).toBe('false')
  })

  it('opens and closes, and the arrow and its name change with the state', () => {
    const { container } = render(<CardDetails><p>Dentro</p></CardDetails>)
    const details = container.querySelector('details') as HTMLDetailsElement
    const summary = container.querySelector('summary') as HTMLElement
    details.open = true
    fireEvent(details, new Event('toggle'))
    expect(summary.getAttribute('aria-expanded')).toBe('true')
    expect(summary.getAttribute('aria-label')).toBe('Ocultar detalle')
    expect(details.className).toContain('is-open')                     // the CSS turns the arrow over
    details.open = false
    fireEvent(details, new Event('toggle'))
    expect(summary.getAttribute('aria-label')).toBe('Ver detalle')
    expect(details.className).not.toContain('is-open')
  })

  it('has the content inside the details', () => {
    const { container } = render(<CardDetails><p>Dentro</p></CardDetails>)
    expect(container.querySelector('details')?.contains(screen.getByText('Dentro'))).toBe(true)
  })
})
