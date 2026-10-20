import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import AlertList, { type AlertEntry } from './AlertList'
import Scoreboard from './Scoreboard'
import { fakeEngine, loadDemo } from './appTestKit'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

const entry = (key: string, severity: 'critical' | 'warning' | 'info' = 'warning'): AlertEntry => ({
  at: 'Q1 08:00', alert: { key, id: key, severity, category: 'faltas', message: key, evidence: {}, proposal: [], rearm_s: null },
})
const OWN = { id: '1', name: 'PROPIO' }
const RIVAL = { id: '2', name: 'RIVAL' }

beforeEach(() => {
  localStorage.clear()
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

// Issue #312: the app felt static. Motion that says what changed, never during the match noise, and off for who asks for less motion.
describe('motion (issue #312)', () => {
  it('a new alert enters with a highlight, the ones already there do not move', () => {
    const { rerender } = render(<AlertList entries={[entry('old')]} />)
    expect(document.querySelectorAll('.alert-new')).toHaveLength(0)             // the first render: nothing is new
    rerender(<AlertList entries={[entry('fresh', 'critical'), entry('old')]} />)
    const fresh = document.querySelectorAll('.alert-new')
    expect(fresh).toHaveLength(1)
    expect(fresh[0].textContent).toContain('fresh')
    rerender(<AlertList entries={[entry('fresh', 'critical'), entry('old')]} />)
    expect(document.querySelectorAll('.alert-new')).toHaveLength(1)              // it stays marked while it is the latest...
    rerender(<AlertList entries={[entry('newer'), entry('fresh', 'critical'), entry('old')]} />)
    expect(document.querySelectorAll('.alert-new')).toHaveLength(1)
    expect(document.querySelector('.alert-new')?.textContent).toContain('newer')  // ...and only the latest ones are
  })

  it('the score flashes when it changes, not at the first paint', () => {
    const { rerender } = render(<Scoreboard own={OWN} rival={RIVAL} homeId="1" score={{ '1': 10, '2': 8 }} clock="Q1 05:00" />)
    expect(document.querySelectorAll('.pts.bump')).toHaveLength(0)
    rerender(<Scoreboard own={OWN} rival={RIVAL} homeId="1" score={{ '1': 12, '2': 8 }} clock="Q1 04:40" />)
    const bumped = document.querySelectorAll('.pts.bump')
    expect(bumped).toHaveLength(1)
    expect(bumped[0].textContent).toBe('12')
  })

  it('the panel of a tab fades in when the tab changes', async () => {
    render(<App engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    const before = screen.getByRole('tabpanel')
    fireEvent.click(screen.getByRole('tab', { name: 'Partidos' }))
    const after = screen.getByRole('tabpanel')
    expect(after.classList.contains('tab-fade')).toBe(true)
    expect(after).not.toBe(before)                                                // keyed by tab: a new element, so the animation plays
  })

  it('has the animations and a way out for who asks for less motion', () => {
    for (const name of ['alert-in', 'score-bump', 'tab-in']) expect(css).toContain(`@keyframes ${name}`)
    const reduced = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'))
    for (const selector of ['.alert-new', '.pts.bump', '.tab-fade']) expect(reduced).toContain(selector)
  })

  it('buttons answer to the touch', () => {
    expect(css).toMatch(/button:active[^{]*\{[^}]*transform: scale\(0\.9\d?\)/)
  })
})
