import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BEAT_KEY, LOG_KEY, MAX_EVENTS, beat, formatSession, markStartup, readSession, recordSession } from './sessionLog'

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('session log (issue #309): what happened to the match, to tell a tap from a restart of the app', () => {
  it('keeps the events in order and only the latest ones', () => {
    for (let i = 0; i < MAX_EVENTS + 5; i++) recordSession(`evento ${i}`, 1_000 + i)
    const events = readSession()
    expect(events).toHaveLength(MAX_EVENTS)
    expect(events[0].text).toBe('evento 5')
    expect(events[events.length - 1].text).toBe(`evento ${MAX_EVENTS + 4}`)
  })

  it('writes a line with the time and the text', () => {
    const line = formatSession({ t: new Date(2026, 9, 14, 16, 5, 12).getTime(), text: 'Partido reiniciado' })
    expect(line).toMatch(/16:05:12/)
    expect(line).toContain('Partido reiniciado')
  })

  it('the startup says when the app was alive seconds before: a restart nobody asked for', () => {
    beat(10_000)
    markStartup(14_000)
    const text = readSession().at(-1)!.text
    expect(text).toMatch(/arranque/i)
    expect(text).toMatch(/4 s/)
    expect(text).toMatch(/reinicio no pedido/i)
  })

  it('a normal start, long after the last beat or with none, is just a start', () => {
    markStartup(1_000)
    expect(readSession().at(-1)!.text).not.toMatch(/no pedido/i)
    beat(1_000)
    markStartup(1_000 + 3 * 3600_000)
    expect(readSession().at(-1)!.text).not.toMatch(/no pedido/i)
  })

  it('ignores a corrupted log', () => {
    localStorage.setItem(LOG_KEY, '{no es json')
    localStorage.setItem(BEAT_KEY, 'zzz')
    expect(readSession()).toEqual([])
    expect(() => markStartup()).not.toThrow()
  })

  // last: the stubbed storage stays for the rest of the file (the global setup clears the real one after each test)
  it('works without storage', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } })
    expect(() => { recordSession('x'); beat(); markStartup() }).not.toThrow()
    expect(readSession()).toEqual([])
  })
})
