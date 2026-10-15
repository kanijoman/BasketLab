import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FormationStatus from './FormationStatus'
import type { FormationStatus as Status } from '../engine/types'

const rivalOf = (known: boolean) => ({ known, on_court: known ? 3 : null, unknown: 0, players: known ? 5 : 0 })
const status = (over: Partial<Status> = {}): Status => ({ min: 2, known: true, on_court: 3, unknown: 0, players: 5, rival: rivalOf(true), ...over })
const OWN = { id: '1', name: 'MIPELLETYMAS B.F. LEON' }
const RIVAL = { id: '2', name: 'RECOLETAS ZAMORA' }

// Issue #322: the lineup is watched for BOTH teams and an illegal one is a critical alert; a card under the scoreboard that is always
// there says nothing. The only thing worth a line is that a team is NOT watched (no roster in the package).
describe('FormationStatus: only says when a team is not being watched (issue #322)', () => {
  it('shows nothing while both teams are watched, whatever the count', () => {
    for (const on_court of [0, 1, 2, 3, 5]) {
      const { container, unmount } = render(<FormationStatus formation={status({ on_court })} own={OWN} rival={RIVAL} />)
      expect(container.innerHTML, String(on_court)).toBe('')
      unmount()
    }
  })

  it('shows nothing when the competition has no such rule or the engine sent nothing', () => {
    expect(render(<FormationStatus formation={status({ min: 0 })} own={OWN} rival={RIVAL} />).container.innerHTML).toBe('')
    expect(render(<FormationStatus formation={null} own={OWN} rival={RIVAL} />).container.innerHTML).toBe('')
  })

  it('says it when our team has no roster', () => {
    render(<FormationStatus formation={status({ known: false, on_court: null })} own={OWN} rival={RIVAL} />)
    expect(screen.getByRole('status').textContent).toMatch(/no se vigila la alineación de formación de MIPELLETYMAS B\.F\. LEON/i)
  })

  it('says it when the rival has no roster', () => {
    render(<FormationStatus formation={status({ rival: rivalOf(false) })} own={OWN} rival={RIVAL} />)
    expect(screen.getByRole('status').textContent).toMatch(/no se vigila la alineación de formación de RECOLETAS ZAMORA/i)
  })

  it('names both when neither is watched', () => {
    render(<FormationStatus formation={status({ known: false, on_court: null, rival: rivalOf(false) })} own={OWN} rival={RIVAL} />)
    const text = screen.getByRole('status').textContent ?? ''
    expect(text).toContain('MIPELLETYMAS B.F. LEON')
    expect(text).toContain('RECOLETAS ZAMORA')
  })

  it('an engine that does not send the rival yet (an old package) only talks about our team', () => {
    const old = { min: 2, known: true, on_court: 2, unknown: 0, players: 5 } as Status
    expect(render(<FormationStatus formation={old} own={OWN} rival={RIVAL} />).container.innerHTML).toBe('')
  })
})
