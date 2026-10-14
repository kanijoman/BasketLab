import { fireEvent, render, screen, within } from '@testing-library/react'
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

  it('collapses the informative ones behind a summary and opens them on demand', () => {
    render(<AlertList entries={MIX} />)
    const details = screen.getByText('2 informativas', { selector: 'summary' }).closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    fireEvent.click(screen.getByText('2 informativas', { selector: 'summary' }))
    details.open = true
    expect(within(details).getAllByRole('listitem').filter(li => li.classList.contains('alert-info'))).toHaveLength(2)
  })

  it('without informative alerts there is no collapsed block', () => {
    render(<AlertList entries={[entry('c1', 'critical')]} />)
    expect(document.querySelector('details')).toBeNull()
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
    expect(Object.keys(CATEGORY_LABEL).sort()).toEqual(['alineacion', 'descanso', 'faltas', 'four_factors', 'gestion', 'rival', 'rotacion'])
    render(<AlertList entries={[entry('x', 'warning', 'nueva')]} />)
    expect(screen.getByText('nueva')).toBeTruthy()
  })
})
