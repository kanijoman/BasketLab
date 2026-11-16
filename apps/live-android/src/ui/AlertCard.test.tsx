import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import AlertCard, { formatProposal } from './AlertCard'
import type { Alert } from '../engine/types'

const ALERT: Alert = {
  key: 'fatigue:1', id: 'fatigue_high', severity: 'warning', category: 'rotacion', message: 'Ana: riesgo de fatiga alto',
  evidence: {}, proposal: [], rearm_s: null,
}

describe('AlertCard dismissal (issue #933, feedback of 2536159: the answers of the staff are gone, a bin icon dismisses)', () => {
  it('has no dismiss button when nobody listens', () => {
    render(<ul><AlertCard alert={ALERT} at="Q1 08:00" /></ul>)
    expect(screen.queryByRole('button', { name: 'Descartar aviso' })).toBeNull()
  })

  it('has an icon button that dismisses the alert, and none of the old answers', () => {
    const onDismiss = vi.fn()
    render(<ul><AlertCard alert={ALERT} at="Q1 08:00" onDismiss={onDismiss} /></ul>)
    const button = screen.getByRole('button', { name: 'Descartar aviso' })
    expect(button.textContent).toBe('')            // an icon, no word
    fireEvent.click(button)
    expect(onDismiss).toHaveBeenCalledTimes(1)
    for (const old of ['Seguida', 'Descartada', 'Ya hecho']) expect(screen.queryByRole('button', { name: old })).toBeNull()
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

describe('AlertCard category of the win-probability flip (issue #258)', () => {
  it('shows «Probabilidad» with its own icon and colour', () => {
    const alert: Alert = { ...ALERT, key: 'win_flip', id: 'win_flip', severity: 'warning', category: 'probabilidad',
      message: 'La probabilidad de victoria ha caído de 62% a 38% en los últimos 5 min (experimental).' }
    render(<ul><AlertCard alert={alert} at="Q2 05:00" /></ul>)
    const tag = screen.getByText('Probabilidad').closest('[data-category]') as HTMLElement
    expect(tag.getAttribute('data-category')).toBe('probabilidad')
    expect(tag.querySelector('svg')).toBeTruthy()
  })
})

describe('AlertCard category of the rest rule (issue #273)', () => {
  it('shows «Descanso» with its own icon and colour', () => {
    const alert: Alert = { ...ALERT, key: 'rest:p1', id: 'rest_starters', category: 'descanso',
      message: 'Partido decidido (+22): descansa a Ana (28 min hoy) y da minutos a Bea (sin minutos hoy).' }
    render(<ul><AlertCard alert={alert} at="Q4 05:00" /></ul>)
    const tag = screen.getByText('Descanso').closest('[data-category]') as HTMLElement
    expect(tag.getAttribute('data-category')).toBe('descanso')
    expect(tag.querySelector('svg')).toBeTruthy()
  })
})

describe('AlertCard category of the period summary (issue #246)', () => {
  it('shows «Resumen» with its own icon and colour', () => {
    const alert: Alert = { ...ALERT, key: 'summary:1', id: 'period_summary', severity: 'info', category: 'resumen',
      message: 'Fin del 1.er cuarto: 18-12 (+6). Claves: Pérdidas: 6 vs 1. Ajustes: Asegurar el balón en la salida de pista.' }
    render(<ul><AlertCard alert={alert} at="Q1 00:00" /></ul>)
    const tag = screen.getByText('Resumen').closest('[data-category]') as HTMLElement
    expect(tag.getAttribute('data-category')).toBe('resumen')
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
