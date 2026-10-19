import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AlertList, { CATEGORY_LABEL, type AlertEntry } from './AlertList'
import type { Alert } from '../engine/types'

const entry = (key: string, severity: Alert['severity'], category = 'faltas', message = key, at = 'Q1 08:00'): AlertEntry => ({
  at,
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
    expect(document.querySelectorAll('details.alert-period')).toHaveLength(1)                 // all of them in the same quarter
    expect(screen.queryByRole('region', { name: 'Informativas' })).toBeNull()
  })

  it('the severity is a mark of each alert, in its own colour', () => {
    render(<AlertList entries={MIX} />)
    const classes = screen.getAllByRole('listitem').filter(li => li.classList.contains('alert')).map(li => [...li.classList].find(c => c.startsWith('alert-') && c !== 'alert-body'))
    expect(classes).toEqual(['alert-warning', 'alert-info', 'alert-critical', 'alert-warning', 'alert-info'])
  })

  it('a new alert goes on top of the flow', () => {
    const { rerender } = render(<AlertList entries={[entry('old', 'warning')]} />)
    rerender(<AlertList entries={[entry('new', 'critical'), entry('old', 'warning')]} />)
    const first = document.querySelector('.alert-list .alerts > li .alert-message')
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
    expect(Object.keys(CATEGORY_LABEL).sort()).toEqual(['alineacion', 'descanso', 'faltas', 'four_factors', 'gestion', 'probabilidad', 'resumen', 'rival', 'rotacion'])
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


// #406: the alerts are grouped by quarter, each group can be folded, and the previous quarter folds by itself 2 minutes into the next
describe('alerts grouped by quarter (issue #406)', () => {
  const FLOW = [
    entry('q3b', 'warning', 'faltas', 'q3b', 'Q3 08:00'), entry('q3a', 'info', 'rival', 'q3a', 'Q3 09:30'),
    entry('q2a', 'warning', 'gestion', 'q2a', 'Q2 01:00'), entry('q1a', 'critical', 'faltas', 'q1a', 'Q1 02:00'),
  ]
  const group = (title: RegExp) => screen.getByText(title, { selector: 'summary' }).closest('details') as HTMLDetailsElement
  const clock = (period: number, remaining: number) => ({ period, remaining })

  it('has one group per quarter, the latest first, with its title and its number of alerts', () => {
    render(<AlertList entries={FLOW} clock={clock(3, 480)} />)
    const titles = [...document.querySelectorAll('details.alert-period > summary')].map(s => s.textContent)
    expect(titles).toEqual(['Cuarto 3 · 2 alertas', 'Cuarto 2 · 1 alerta', 'Cuarto 1 · 1 alerta'])
  })

  it('the current quarter is open; the previous one stays open during the first 2 minutes of the next, then folds', () => {
    const { rerender } = render(<AlertList entries={FLOW} clock={clock(3, 600 - 119)} />)
    expect(group(/Cuarto 3/).open).toBe(true)
    expect(group(/Cuarto 2/).open).toBe(true)
    expect(group(/Cuarto 1/).open).toBe(false)
    rerender(<AlertList entries={FLOW} clock={clock(3, 600 - 120)} />)
    expect(group(/Cuarto 3/).open).toBe(true)
    expect(group(/Cuarto 2/).open).toBe(false)
  })

  it('the staff can fold the current quarter and open an old one, and the choice survives the clock moving on', () => {
    const { rerender } = render(<AlertList entries={FLOW} clock={clock(3, 400)} />)
    fireEvent.click(screen.getByText(/Cuarto 3/, { selector: 'summary' }))
    fireEvent.click(screen.getByText(/Cuarto 1/, { selector: 'summary' }))
    expect(group(/Cuarto 3/).open).toBe(false)
    expect(group(/Cuarto 1/).open).toBe(true)
    rerender(<AlertList entries={FLOW} clock={clock(3, 300)} />)
    expect(group(/Cuarto 3/).open).toBe(false)
    expect(group(/Cuarto 1/).open).toBe(true)
    fireEvent.click(screen.getByText(/Cuarto 3/, { selector: 'summary' }))
    expect(group(/Cuarto 3/).open).toBe(true)
  })

  it('overtime periods are named as such, and the filter works inside the groups', () => {
    render(<AlertList entries={[entry('p1', 'warning', 'faltas', 'p1', 'PR1 03:10'), entry('q4', 'info', 'rival', 'q4', 'Q4 00:30')]} clock={clock(5, 200)} />)
    expect(screen.getByText('Prórroga 1 · 1 alerta', { selector: 'summary' })).toBeTruthy()
    expect(screen.getByText('Cuarto 4 · 1 alerta', { selector: 'summary' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '1 informativa' }))
    expect(screen.queryByText(/Cuarto 4/, { selector: 'summary' })).toBeNull()      // a group with every alert hidden disappears
  })

  it('without a clock the newest alert says which quarter is the current one', () => {
    render(<AlertList entries={FLOW} />)
    expect(group(/Cuarto 3/).open).toBe(true)
    expect(group(/Cuarto 1/).open).toBe(false)
  })
})
