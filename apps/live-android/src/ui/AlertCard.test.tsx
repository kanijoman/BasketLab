import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import AlertCard from './AlertCard'
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
