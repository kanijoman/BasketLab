import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FormationStatus from './FormationStatus'
import type { FormationStatus as Status } from '../engine/types'

const status = (over: Partial<Status> = {}): Status => ({ min: 2, known: true, on_court: 3, unknown: 0, players: 5, ...over })

describe('FormationStatus (issue #272)', () => {
  it('shows how many formación players are on court against the minimum', () => {
    render(<FormationStatus formation={status()} />)
    expect(screen.getByText(/formación en pista: 3 \(mínimo 2\)/i)).toBeTruthy()
    expect(document.querySelector('.formation-status')?.getAttribute('data-state')).toBe('ok')
  })

  it('at the minimum it is fine but says so', () => {
    render(<FormationStatus formation={status({ on_court: 2 })} />)
    expect(document.querySelector('.formation-status')?.getAttribute('data-state')).toBe('limit')
  })

  it('below the minimum with a full lineup is an illegal lineup and is announced to assistive technology', () => {
    render(<FormationStatus formation={status({ on_court: 1 })} />)
    const el = screen.getByRole('alert')
    expect(el.textContent).toMatch(/por debajo del mínimo/i)
    expect(el.getAttribute('data-state')).toBe('bad')
  })

  it('with a substitution in progress (fewer than five on court) it does not shout', () => {
    render(<FormationStatus formation={status({ on_court: 0, players: 4 })} />)
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText(/cambio en curso/i)).toBeTruthy()
  })

  it('players the roster does not know give the benefit of the doubt and are mentioned', () => {
    render(<FormationStatus formation={status({ on_court: 1, unknown: 2 })} />)
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText(/2 sin datos/i)).toBeTruthy()
  })

  it('says it is not watching the lineup when the package has no roster', () => {
    render(<FormationStatus formation={status({ known: false, on_court: null })} />)
    expect(screen.getByText(/sin plantilla de feb/i)).toBeTruthy()
    expect(screen.getByText(/no se vigila/i)).toBeTruthy()
  })

  it('shows nothing without the data or when the competition has no such rule', () => {
    const { container, rerender } = render(<FormationStatus formation={undefined} />)
    expect(container.firstChild).toBeNull()
    rerender(<FormationStatus formation={status({ min: 0 })} />)
    expect(container.firstChild).toBeNull()
  })
})

describe('FormationStatus says whose lineup it is (issue #322: it was not clear if it was ours or the rival)', () => {
  const own = { id: '1', name: 'MIPELLETYMAS B.F. LEON' }

  it('names the own team', () => {
    render(<FormationStatus formation={status()} team={own} />)
    const el = document.querySelector('.formation-status') as HTMLElement
    expect(el.textContent).toMatch(/tu equipo/i)
    expect(el.textContent).toContain('MIPELLETYMAS B.F. LEON')
    expect(el.textContent).toMatch(/formación en pista: 3 \(mínimo 2\)/i)
  })

  it('also when it is not being watched, and when the lineup is illegal', () => {
    const { rerender } = render(<FormationStatus formation={status({ known: false, on_court: null })} team={own} />)
    expect(document.querySelector('.formation-status')?.textContent).toMatch(/tu equipo/i)
    rerender(<FormationStatus formation={status({ on_court: 1 })} team={own} />)
    expect(screen.getByRole('alert').textContent).toMatch(/tu equipo/i)
  })
})
