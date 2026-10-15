import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ALERT_MODE_KEY, ALERT_MODES, useAlertMode } from './useAlertMode'

// Issue #130: the staff picks how many alerts it wants (aggressive, medium, conservative), not thresholds.
describe('useAlertMode', () => {
  it('is medium until the staff chooses, and remembers the choice', () => {
    const { result, unmount } = renderHook(() => useAlertMode())
    expect(result.current[0]).toBe('medium')
    act(() => result.current[1]('aggressive'))
    expect(result.current[0]).toBe('aggressive')
    expect(localStorage.getItem(ALERT_MODE_KEY)).toBe('aggressive')
    unmount()
    expect(renderHook(() => useAlertMode()).result.current[0]).toBe('aggressive')
  })

  it('has the three modes with a plain-language description each', () => {
    expect(ALERT_MODES.map(m => m.id)).toEqual(['aggressive', 'medium', 'conservative'])
    expect(ALERT_MODES.map(m => m.label)).toEqual(['Agresivo', 'Medio', 'Conservador'])
    expect(ALERT_MODES.every(m => m.help.length > 20)).toBe(true)
  })

  it('ignores an unknown stored value', () => {
    localStorage.setItem(ALERT_MODE_KEY, 'loud')
    expect(renderHook(() => useAlertMode()).result.current[0]).toBe('medium')
  })

  // last: the stubbed storage stays for the rest of the file
  it('works without storage', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } })
    const { result } = renderHook(() => useAlertMode())
    expect(result.current[0]).toBe('medium')
    expect(() => act(() => result.current[1]('conservative'))).not.toThrow()
    expect(result.current[0]).toBe('conservative')
  })
})
