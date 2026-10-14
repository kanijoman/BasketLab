import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import TabBar from './TabBar'
import { TAB_KEY, useTab } from './useTab'

describe('TabBar (issue #224)', () => {
  it('has the three tabs in order with the active one selected', () => {
    render(<TabBar active="paquetes" onChange={() => undefined} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Partido', 'Paquetes', 'Acerca de'])
    expect(tabs.map(t => t.getAttribute('aria-selected'))).toEqual(['false', 'true', 'false'])
    expect(screen.getByRole('tablist', { name: 'Secciones' })).toBeTruthy()
  })

  it('reports the tab the user presses and gives each one an icon', () => {
    const onChange = vi.fn()
    render(<TabBar active="partido" onChange={onChange} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    expect(onChange).toHaveBeenCalledWith('acerca')
    screen.getAllByRole('tab').forEach(t => expect(t.querySelector('svg')).toBeTruthy())
  })
})

describe('useTab (issue #224)', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('starts on the match tab', () => {
    expect(renderHook(() => useTab()).result.current[0]).toBe('partido')
  })

  it('remembers the active tab', () => {
    const first = renderHook(() => useTab())
    act(() => first.result.current[1]('paquetes'))
    expect(first.result.current[0]).toBe('paquetes')
    expect(localStorage.getItem(TAB_KEY)).toBe('paquetes')
    expect(renderHook(() => useTab()).result.current[0]).toBe('paquetes')
  })

  it('ignores a stored value that is not a tab', () => {
    localStorage.setItem(TAB_KEY, 'otra-cosa')
    expect(renderHook(() => useTab()).result.current[0]).toBe('partido')
  })

  it('works when the storage is not available', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    const hook = renderHook(() => useTab())
    expect(hook.result.current[0]).toBe('partido')
    act(() => hook.result.current[1]('acerca'))
    expect(hook.result.current[0]).toBe('acerca')
  })
})
