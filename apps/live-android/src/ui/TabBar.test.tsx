import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import TabBar from './TabBar'
import { useTab } from './useTab'

describe('TabBar (issue #224)', () => {
  it('has the four tabs in order with the active one selected', () => {
    render(<TabBar active="paquetes" onChange={() => undefined} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map(t => t.textContent)).toEqual(['Partido', 'Boxscore', 'Partidos', 'Acerca de'])
    expect(tabs.map(t => t.getAttribute('aria-selected'))).toEqual(['false', 'false', 'true', 'false'])
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

describe('useTab', () => {
  it('opens on the list of matches (Partidos), whatever was used last', () => {
    expect(renderHook(() => useTab()).result.current[0]).toBe('paquetes')
  })

  it('can start on another tab (tests) and changes', () => {
    const hook = renderHook(() => useTab('partido'))
    expect(hook.result.current[0]).toBe('partido')
    act(() => hook.result.current[1]('acerca'))
    expect(hook.result.current[0]).toBe('acerca')
  })
})
