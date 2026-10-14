import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import AlertCard, { formatProposal } from './AlertCard'
import type { Alert } from '../engine/types'

const ALERT: Alert = {
  key: 'fatigue:1', id: 'fatigue_high', severity: 'warning', category: 'rotacion', message: 'Ana: riesgo de fatiga alto',
  evidence: {}, proposal: [], rearm_s: null,
}

describe('AlertCard feedback (issue #235)', () => {
  it('has no feedback buttons when nobody listens', () => {
    render(<ul><AlertCard alert={ALERT} at="Q1 08:00" /></ul>)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('offers the three answers, none pressed at first', () => {
    render(<ul><AlertCard alert={ALERT} at="Q1 08:00" verdict={null} onVerdict={() => undefined} /></ul>)
    const group = screen.getByRole('group', { name: /qué se hizo/i })
    const buttons = within(group).getAllByRole('button')
    expect(buttons.map(b => b.textContent)).toEqual(['Seguida', 'Descartada', 'Ya hecho'])
    expect(buttons.map(b => b.getAttribute('aria-pressed'))).toEqual(['false', 'false', 'false'])
  })

  it('reports the answer and marks the chosen one as pressed', () => {
    const onVerdict = vi.fn()
    const { rerender } = render(<ul><AlertCard alert={ALERT} at="Q1 08:00" verdict={null} onVerdict={onVerdict} /></ul>)
    fireEvent.click(screen.getByRole('button', { name: 'Descartada' }))
    expect(onVerdict).toHaveBeenCalledWith('descartada')
    rerender(<ul><AlertCard alert={ALERT} at="Q1 08:00" verdict="descartada" onVerdict={onVerdict} /></ul>)
    expect(screen.getByRole('button', { name: 'Descartada' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: 'Seguida' }).getAttribute('aria-pressed')).toBe('false')
  })

  it('pressing the chosen answer again takes it back', () => {
    const onVerdict = vi.fn()
    render(<ul><AlertCard alert={ALERT} at="Q1 08:00" verdict="seguida" onVerdict={onVerdict} /></ul>)
    fireEvent.click(screen.getByRole('button', { name: 'Seguida' }))
    expect(onVerdict).toHaveBeenCalledWith(null)
  })
})

describe('AlertCard category of the lineup rule (issue #272)', () => {
  it('shows «Alineación» with its own icon and colour', () => {
    const alert: Alert = { ...ALERT, key: 'formation:p1', id: 'formation_lineup', severity: 'critical', category: 'alineacion',
      message: 'Alineación indebida: solo 1 de formación en pista (mínimo 2).' }
    render(<ul><AlertCard alert={alert} at="Q3 05:00" /></ul>)
    const tag = screen.getByText('Alineación').closest('[data-category]') as HTMLElement
    expect(tag.getAttribute('data-category')).toBe('alineacion')
    expect(tag.querySelector('svg')).toBeTruthy()
  })
})

describe('proposal kinds (issue #240)', () => {
  const withProposal = (...proposal: Alert['proposal']): Alert => ({ ...ALERT, proposal })

  it('formats a substitution as out → in, as before', () => {
    expect(formatProposal({ type: 'sub', out_name: 'Ana', in_name: 'Bea' })).toBe('Ana → Bea')
  })

  it('formats a timeout with the timeouts left', () => {
    expect(formatProposal({ type: 'timeout', left: 2 })).toBe('Tiempo muerto · quedan 2')
    expect(formatProposal({ type: 'timeout', left: 1 })).toBe('Tiempo muerto · queda 1')
    expect(formatProposal({ type: 'timeout', left: 0 })).toBe('Tiempo muerto · no quedan')
    expect(formatProposal({ type: 'timeout' })).toBe('Tiempo muerto')
  })

  it('formats a tactic with its message and, if any, its target player', () => {
    expect(formatProposal({ type: 'tactic', message: 'Defensa en zona' })).toBe('Defensa en zona')
    expect(formatProposal({ type: 'tactic', message: 'Ayudas sobre ella', player_name: 'Rita' })).toBe('Rita: Ayudas sobre ella')
  })

  it('shows an unknown kind by its message, or by its type if it has none', () => {
    expect(formatProposal({ type: 'futuro', message: 'Algo nuevo' })).toBe('Algo nuevo')
    expect(formatProposal({ type: 'futuro' })).toBe('futuro')
  })

  it('renders every kind in the card, each with its kind and an icon', () => {
    render(<ul><AlertCard at="Q2 05:00" alert={withProposal(
      { type: 'timeout', left: 2 }, { type: 'tactic', message: 'Zona 2-3' }, { type: 'sub', out_name: 'Ana', in_name: 'Bea' },
    )} /></ul>)
    const items = within(screen.getByRole('list', { name: 'Propuestas' })).getAllByRole('listitem')
    expect(items.map(i => i.textContent)).toEqual(['Tiempo muerto · quedan 2', 'Zona 2-3', 'Ana → Bea'])
    expect(items.map(i => i.getAttribute('data-kind'))).toEqual(['timeout', 'tactic', 'sub'])
    items.forEach(i => expect(i.querySelector('svg')).not.toBeNull())
  })
})
