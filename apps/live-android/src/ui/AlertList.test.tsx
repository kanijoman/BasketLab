import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AlertList, { CATEGORY_LABEL, type AlertEntry } from './AlertList'
import type { Alert } from '../engine/types'

const entry = (key: string, severity: Alert['severity'], category = 'faltas', message = key): AlertEntry => ({
  at: 'Q1 08:00',
  alert: { key, id: key, severity, category, message, evidence: {}, proposal: [], rearm_s: null },
})

const MIX = [
  entry('w1', 'warning', 'gestion'),
  entry('i1', 'info', 'rival'),
  entry('c1', 'critical', 'faltas'),
  entry('w2', 'warning', 'rotacion'),
  entry('i2', 'info', 'four_factors'),
]

describe('AlertList (issue #229)', () => {
  it('counts the alerts per level in the header', () => {
    render(<AlertList entries={MIX} />)
    const counts = screen.getByLabelText('Resumen de alertas')
    expect(within(counts).getByText('1 crítica')).toBeTruthy()
    expect(within(counts).getByText('2 avisos')).toBeTruthy()
    expect(within(counts).getByText('2 informativas')).toBeTruthy()
  })

  it('pins the critical ones on top, then the warnings, keeping the order of arrival inside a level', () => {
    render(<AlertList entries={MIX} />)
    const shown = screen.getAllByRole('listitem').filter(li => li.classList.contains('alert'))
    expect(shown.slice(0, 3).map(li => li.querySelector('.alert-message')?.textContent)).toEqual(['c1', 'w1', 'w2'])
  })

  it('shows the informative ones always, under their own heading (issue #309: collapsed they were overlooked)', () => {
    render(<AlertList entries={MIX} />)
    expect(document.querySelector('details')).toBeNull()
    const block = screen.getByRole('region', { name: 'Informativas' })
    expect(within(block).getByRole('heading', { name: 'Informativas (2)' })).toBeTruthy()
    expect(within(block).getAllByRole('listitem').filter(li => li.classList.contains('alert-info'))).toHaveLength(2)
  })

  it('without informative alerts there is no informative block', () => {
    render(<AlertList entries={[entry('c1', 'critical')]} />)
    expect(screen.queryByRole('region', { name: 'Informativas' })).toBeNull()
    expect(screen.getByText('1 crítica')).toBeTruthy()
    expect(screen.queryByText(/informativa/)).toBeNull()
  })

  it('uses the singular for one informative alert', () => {
    render(<AlertList entries={[entry('i1', 'info')]} />)
    expect(screen.getAllByText('1 informativa').length).toBeGreaterThan(0)
  })

  it('every card shows its category with its own icon and colour, apart from the severity', () => {
    render(<AlertList entries={MIX} />)
    const card = screen.getByText('c1').closest('li') as HTMLElement
    const tag = within(card).getByText(CATEGORY_LABEL.faltas)
    expect(tag.closest('[data-category]')?.getAttribute('data-category')).toBe('faltas')
    expect(tag.closest('[data-category]')?.querySelector('svg')).toBeTruthy()
    expect(card.classList.contains('alert-critical')).toBe(true)
  })

  it('knows the categories the engine emits and falls back for an unknown one', () => {
    expect(Object.keys(CATEGORY_LABEL).sort()).toEqual(['alineacion', 'descanso', 'faltas', 'four_factors', 'gestion', 'resumen', 'rival', 'rotacion'])
    render(<AlertList entries={[entry('x', 'warning', 'nueva')]} />)
    expect(screen.getByText('nueva')).toBeTruthy()
  })
})
