import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AlertPacer, ALERT_COOLDOWN_MS, MAX_PENDING } from './alertPacer'
import type { AlertEntry } from './AlertList'
import type { Alert } from '../engine/types'

const alert = (key: string, severity: Alert['severity'] = 'warning', message = key): Alert => (
  { key, id: key, severity, category: 'faltas', message, evidence: {}, proposal: [], rearm_s: null }
)

/** A pacer whose shown entries are collected in order, latest release last. */
function setup(hidden = false) {
  const shown: AlertEntry[] = []
  const state = { hidden }
  const pacer = new AlertPacer(items => { shown.push(...items) }, { isHidden: () => state.hidden })
  return { pacer, shown, state, keys: () => shown.map(e => e.alert.key) }
}

describe('AlertPacer (issue #375): a burst of alerts is read one by one', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(1_000_000) })
  afterEach(() => { vi.useRealTimers() })

  it('shows the first alert at once and the others every 3 seconds', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('a'), alert('b'), alert('c')], 'Q1 08:00', true)

    expect(ALERT_COOLDOWN_MS).toBe(3000)
    expect(keys()).toEqual(['a'])
    vi.advanceTimersByTime(2999)
    expect(keys()).toEqual(['a'])
    vi.advanceTimersByTime(1)
    expect(keys()).toEqual(['a', 'b'])
    vi.advanceTimersByTime(3000)
    expect(keys()).toEqual(['a', 'b', 'c'])
  })

  it('keeps the time of the burst on every alert', () => {
    const { pacer, shown } = setup()
    pacer.push([alert('a'), alert('b')], 'Q2 05:30', true)
    vi.advanceTimersByTime(3000)

    expect(shown.map(e => e.at)).toEqual(['Q2 05:30', 'Q2 05:30'])
  })

  it('orders a burst by severity, then by the order of the engine; the critical one does not wait and restarts the clock', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('i1', 'info'), alert('w1', 'warning'), alert('c1', 'critical'), alert('w2', 'warning')], 'Q1 08:00', true)

    expect(keys()).toEqual(['c1'])
    vi.advanceTimersByTime(3000)
    expect(keys()).toEqual(['c1', 'w1'])
    vi.advanceTimersByTime(3000)
    expect(keys()).toEqual(['c1', 'w1', 'w2'])
    vi.advanceTimersByTime(3000)
    expect(keys()).toEqual(['c1', 'w1', 'w2', 'i1'])
  })

  it('a critical alert is shown at once even in the middle of the cooldown, and restarts the clock', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('a'), alert('b')], 'Q1 08:00', true)         // a now, b at +3 s
    vi.advanceTimersByTime(1000)
    pacer.push([alert('c', 'critical')], 'Q1 07:50', true)         // at +1 s, at once
    expect(keys()).toEqual(['a', 'c'])
    vi.advanceTimersByTime(2999)                                    // b would have been at +3 s but the clock restarted at +1 s
    expect(keys()).toEqual(['a', 'c'])
    vi.advanceTimersByTime(1)
    expect(keys()).toEqual(['a', 'c', 'b'])
  })

  it('an alert that arrives after the cooldown is shown at once', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('a')], 'Q1 08:00', true)
    vi.advanceTimersByTime(ALERT_COOLDOWN_MS + 1)
    pacer.push([alert('b')], 'Q1 07:00', true)

    expect(keys()).toEqual(['a', 'b'])
  })

  it('an alert that arrives inside the cooldown waits for what is left of it', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('a')], 'Q1 08:00', true)
    vi.advanceTimersByTime(1200)
    pacer.push([alert('b')], 'Q1 07:55', true)

    expect(keys()).toEqual(['a'])
    vi.advanceTimersByTime(1799)
    expect(keys()).toEqual(['a'])
    vi.advanceTimersByTime(1)
    expect(keys()).toEqual(['a', 'b'])
  })

  it('what is not paced (a jump in the timeline, a replay, a loaded match) is shown all at once, in the order given', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('a'), alert('b'), alert('c')], 'Q1 08:00', false)

    expect(keys()).toEqual(['a', 'b', 'c'])
  })

  it('shows everything pending as soon as the app goes to the background: nobody is reading', () => {
    const { pacer, keys, state } = setup()
    pacer.push([alert('a'), alert('b'), alert('c')], 'Q1 08:00', true)
    state.hidden = true
    pacer.flush()

    expect(keys()).toEqual(['a', 'b', 'c'])
    vi.advanceTimersByTime(10_000)
    expect(keys()).toEqual(['a', 'b', 'c'])      // and nothing is shown twice
  })

  it('a burst that arrives while the app is hidden is shown at once', () => {
    const { pacer, keys } = setup(true)
    pacer.push([alert('a'), alert('b')], 'Q1 08:00', true)

    expect(keys()).toEqual(['a', 'b'])
  })

  it('past the limit the rest of the burst is grouped in one summary card instead of lagging behind', () => {
    const { pacer, shown, keys } = setup()
    const burst = Array.from({ length: MAX_PENDING + 4 }, (_, i) => alert(`n${i}`, 'warning', `Aviso número ${i}`))
    pacer.push(burst, 'Q3 04:00', true)
    vi.advanceTimersByTime(ALERT_COOLDOWN_MS * (MAX_PENDING + 2))

    expect(MAX_PENDING).toBe(6)
    expect(keys().slice(0, MAX_PENDING)).toEqual(burst.slice(0, MAX_PENDING).map(a => a.key))
    expect(shown).toHaveLength(MAX_PENDING + 1)
    const summary = shown[MAX_PENDING].alert
    expect(summary.category).toBe('resumen')
    expect(summary.severity).toBe('info')
    expect(summary.message).toContain('+4 avisos')
    expect(summary.message).toContain('Aviso número 6')
  })

  it('clear forgets what is pending and its timers (a new match, a restart)', () => {
    const { pacer, keys } = setup()
    pacer.push([alert('a'), alert('b')], 'Q1 08:00', true)
    pacer.clear()
    vi.advanceTimersByTime(10_000)

    expect(keys()).toEqual(['a'])
    pacer.push([alert('x')], 'Q1 05:00', true)
    expect(keys()).toEqual(['a', 'x'])             // the cooldown is not carried over either
  })
})
