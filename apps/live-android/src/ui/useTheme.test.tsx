import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import BrandHeader from './BrandHeader'
import { fakeEngine, loadDemo } from './appTestKit'
import { THEME_KEY, applyStoredTheme, effectiveTheme, useTheme } from './useTheme'

const html = () => document.documentElement

function systemIs(scheme: 'light' | 'dark') {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('light') ? scheme === 'light' : scheme === 'dark', media: query,
    addEventListener: () => undefined, removeEventListener: () => undefined }))
}

beforeEach(() => {
  localStorage.clear()
  html().removeAttribute('data-theme')
  systemIs('dark')
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ v: 1, packages: [] }) }))
})
afterEach(() => vi.useRealTimers())

// Issue #322: the app had a light theme and a dark one in its tokens, but nowhere to choose between them.
describe('theme (issue #322)', () => {
  it('follows the system until the user chooses: no attribute on <html>', () => {
    applyStoredTheme()
    expect(html().getAttribute('data-theme')).toBeNull()
    expect(effectiveTheme('system')).toBe('dark')
    systemIs('light')
    expect(effectiveTheme('system')).toBe('light')
  })

  it('a chosen theme is applied to <html>, remembered, and restored when the app starts', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.setPreference('light'))
    expect(html().getAttribute('data-theme')).toBe('light')
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
    html().removeAttribute('data-theme')
    applyStoredTheme()
    expect(html().getAttribute('data-theme')).toBe('light')
    act(() => result.current.setPreference('system'))
    expect(html().getAttribute('data-theme')).toBeNull()
  })

  it('the quick toggle goes to the opposite of what is on screen, also when it follows the system', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dark')                  // the system is dark
    act(() => result.current.toggle())
    expect(result.current.preference).toBe('light')
    act(() => result.current.toggle())
    expect(result.current.preference).toBe('dark')
  })

  it('ignores a corrupted or unknown stored value', () => {
    localStorage.setItem(THEME_KEY, 'verde')
    applyStoredTheme()
    expect(html().getAttribute('data-theme')).toBeNull()
  })
})

describe('theme controls (issue #322)', () => {
  it('the header has a button that switches between light and dark', () => {
    render(<BrandHeader />)
    const button = screen.getByRole('button', { name: /cambiar a modo claro/i })
    fireEvent.click(button)
    expect(html().getAttribute('data-theme')).toBe('light')
    expect(screen.getByRole('button', { name: /cambiar a modo oscuro/i })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /cambiar a modo oscuro/i }))
    expect(html().getAttribute('data-theme')).toBe('dark')
  })

  it('Acerca de has the choice System, Claro or Oscuro, and it is the same state as the header button', async () => {
    render(<App initialTab="partido" engine={fakeEngine()} loadDemo={loadDemo} />)
    await screen.findByText('EQUIPO PROPIO')
    fireEvent.click(screen.getByRole('tab', { name: 'Acerca de' }))
    const group = screen.getByRole('radiogroup', { name: 'Apariencia' })
    expect((screen.getByRole('radio', { name: 'Sistema' }) as HTMLInputElement).checked).toBe(true)
    fireEvent.click(screen.getByRole('radio', { name: 'Claro' }))
    expect(html().getAttribute('data-theme')).toBe('light')
    expect(group.querySelectorAll('input:checked')).toHaveLength(1)
    expect(screen.getByRole('button', { name: /cambiar a modo oscuro/i })).toBeTruthy()      // the header followed
    fireEvent.click(screen.getByRole('radio', { name: 'Sistema' }))
    expect(html().getAttribute('data-theme')).toBeNull()
  })
})

describe('without storage (issue #322)', () => {
  // last: the stubbed storage stays for the rest of the file (the global setup clears the real one after each test)
  it('works without storage', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('blocked') } })
    expect(() => applyStoredTheme()).not.toThrow()
    const { result } = renderHook(() => useTheme())
    expect(() => act(() => result.current.setPreference('light'))).not.toThrow()
    expect(html().getAttribute('data-theme')).toBe('light')
  })
})
