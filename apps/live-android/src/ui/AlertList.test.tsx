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

  it('is one chronological flow: the order it receives (the latest first), severity is not a grouping (issue #313)', () => {
    render(<AlertList entries={MIX} />)
    const shown = screen.getAllByRole('listitem').filter(li => li.classList.contains('alert'))
    expect(shown.map(li => li.querySelector('.alert-message')?.textContent)).toEqual(['w1', 'i1', 'c1', 'w2', 'i2'])
    expect(document.querySelector('details')).toBeNull()
    expect(screen.queryByRole('region', { name: 'Informativas' })).toBeNull()
  })

  it('the severity is a mark of each alert, in its own colour', () => {
    render(<AlertList entries={MIX} />)
    const classes = screen.getAllByRole('listitem').filter(li => li.classList.contains('alert')).map(li => [...li.classList].find(c => c.startsWith('alert-') && c !== 'alert-body'))
    expect(classes).toEqual(['alert-warning', 'alert-info', 'alert-critical', 'alert-warning', 'alert-info'])
  })

  it('shows the 20 latest and collapses the rest behind «Ver las N anteriores»', () => {
    const many = Array.from({ length: 25 }, (_, i) => entry(`a${i}`, 'warning'))      // a0 is the latest
    render(<AlertList entries={many} />)
    const details = screen.getByText('Ver las 5 anteriores', { selector: 'summary' }).closest('details') as HTMLDetailsElement
    expect(details.open).toBe(false)
    const visible = document.querySelectorAll('.alert-list > .alerts > li')
    expect(visible).toHaveLength(20)
    expect(visible[0].querySelector('.alert-message')?.textContent).toBe('a0')
    expect(visible[19].querySelector('.alert-message')?.textContent).toBe('a19')
    expect(within(details).getAllByRole('listitem').filter(li => li.classList.contains('alert')).map(li => li.querySelector('.alert-message')?.textContent))
      .toEqual(['a20', 'a21', 'a22', 'a23', 'a24'])
  })

  it('with 20 alerts or fewer there is nothing collapsed, and the older one uses the singular', () => {
    render(<AlertList entries={Array.from({ length: 20 }, (_, i) => entry(`a${i}`, 'info'))} />)
    expect(document.querySelector('details')).toBeNull()
    render(<AlertList entries={Array.from({ length: 21 }, (_, i) => entry(`b${i}`, 'info'))} />)
    expect(screen.getByText('Ver la 1 anterior', { selector: 'summary' })).toBeTruthy()
  })

  it('a new alert goes on top of the flow', () => {
    const { rerender } = render(<AlertList entries={[entry('old', 'warning')]} />)
    rerender(<AlertList entries={[entry('new', 'critical'), entry('old', 'warning')]} />)
    const first = document.querySelector('.alert-list > .alerts > li .alert-message')
    expect(first?.textContent).toBe('new')
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

describe('severity filter on the counters (issue #322)', () => {
  const flow = () => Array.from(document.querySelectorAll('.alert-list li.alert')).map(li => li.querySelector('.alert-message')?.textContent)
  const counter = (text: string) => screen.getByRole('button', { name: text })

  it('the counters are toggle buttons, all on at the start', () => {
    render(<AlertList entries={MIX} />)
    for (const name of ['1 crítica', '2 avisos', '2 informativas']) expect(counter(name).getAttribute('aria-pressed')).toBe('true')
    expect(flow()).toEqual(['w1', 'i1', 'c1', 'w2', 'i2'])
  })

  it('pressing one hides that severity and pressing it again shows it, keeping the chronological order', () => {
    render(<AlertList entries={MIX} />)
    fireEvent.click(counter('2 informativas'))
    expect(counter('2 informativas').getAttribute('aria-pressed')).toBe('false')
    expect(flow()).toEqual(['w1', 'c1', 'w2'])
    fireEvent.click(counter('2 avisos'))
    expect(flow()).toEqual(['c1'])
    fireEvent.click(counter('2 informativas'))
    expect(flow()).toEqual(['i1', 'c1', 'i2'])
  })

  it('the counters keep counting everything, hidden or not', () => {
    render(<AlertList entries={MIX} />)
    fireEvent.click(counter('2 avisos'))
    expect(screen.getByRole('button', { name: '2 avisos' })).toBeTruthy()
  })

  it('the filter goes first, then the 20 latest and the rest collapsed', () => {
    const entries = Array.from({ length: 30 }, (_, i) => entry(`a${i}`, i % 3 === 0 ? 'info' : 'warning'))      // 10 info, 20 warnings
    render(<AlertList entries={entries} />)
    expect(screen.getByText('Ver las 10 anteriores', { selector: 'summary' })).toBeTruthy()
    fireEvent.click(counter('10 informativas'))
    expect(document.querySelector('details')).toBeNull()                                   // 20 warnings fit in the 20 visible
    expect(document.querySelectorAll('.alert-list > .alerts > li')).toHaveLength(20)
  })

  it('with every severity hidden it says so and how to get them back', () => {
    render(<AlertList entries={[entry('c1', 'critical')]} />)
    fireEvent.click(counter('1 crítica'))
    expect(screen.getByText(/has ocultado todas las alertas/i)).toBeTruthy()
    fireEvent.click(counter('1 crítica'))
    expect(flow()).toEqual(['c1'])
  })

  it('the filter is remembered for the next time', () => {
    const first = render(<AlertList entries={MIX} />)
    fireEvent.click(counter('2 informativas'))
    first.unmount()
    render(<AlertList entries={MIX} />)
    expect(counter('2 informativas').getAttribute('aria-pressed')).toBe('false')
    expect(flow()).toEqual(['w1', 'c1', 'w2'])
  })
})
