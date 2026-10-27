/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DEFAULT_THEME, THEME_KEY, applyStoredTheme, useTheme } from './theme'

const html = () => document.documentElement
const themeColor = () => document.querySelector('meta[name="theme-color"]')?.getAttribute('content')

function systemIs(scheme: 'light' | 'dark') {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: query.includes('light') ? scheme === 'light' : scheme === 'dark', media: query,
    addEventListener: () => undefined, removeEventListener: () => undefined }))
}

beforeEach(() => {
  localStorage.clear()
  html().removeAttribute('data-theme')
  document.head.innerHTML = '<meta name="theme-color" content="">'
  systemIs('dark')
})

// Issue #188: the web was dark only (<html class="dark"> fixed). It gets light, dark and the system's, light by default (decision of 27/10/2026).
describe('theme of the web (issue #188)', () => {
  it('opens in the light theme when nothing was chosen, even on a dark system', () => {
    applyStoredTheme()
    expect(DEFAULT_THEME).toBe('light')
    expect(html().getAttribute('data-theme')).toBe('light')
    expect(themeColor()).toBe('#f6f8fa')
    expect(renderHook(() => useTheme()).result.current.theme).toBe('light')
  })

  it('remembers what was chosen, and «Sistema» follows the device', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.setPreference('dark'))
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(html().getAttribute('data-theme')).toBe('dark')
    expect(themeColor()).toBe('#0d1117')

    act(() => result.current.setPreference('system'))
    expect(html().getAttribute('data-theme')).toBeNull()      // the tokens follow prefers-color-scheme by themselves
    expect(result.current.theme).toBe('dark')
  })

  it('keeps the choice for the session when the storage is blocked', () => {
    const storage = localStorage
    const blocked = () => { throw new Error('blocked') }
    vi.stubGlobal('localStorage', { getItem: blocked, setItem: blocked, clear: blocked })
    try {
      const { result } = renderHook(() => useTheme())
      act(() => result.current.setPreference('dark'))
      expect(result.current.preference).toBe('dark')
      expect(html().getAttribute('data-theme')).toBe('dark')
    } finally {
      vi.stubGlobal('localStorage', storage)
    }
  })
})

describe('the theme before the first paint (issue #188)', () => {
  // index.html sets the theme in a blocking script, before the CSS paints the page: no flash of the other theme.
  // It cannot import the store, so it repeats its key and default; this keeps both equal.
  const page = readFileSync(join(__dirname, '..', '..', 'index.html'), 'utf8')
  const inline = page.match(/<script>([\s\S]*?)<\/script>/)?.[1] ?? ''

  it.each([[null, 'light'], ['dark', 'dark'], ['light', 'light'], ['system', null], ['garbage', 'light']])(
    'stored %s → data-theme %s, the same as the store', (stored, expected) => {
      if (stored) localStorage.setItem(THEME_KEY, stored)
      new Function(inline)()
      expect(html().getAttribute('data-theme')).toBe(expected)
      html().removeAttribute('data-theme')
      applyStoredTheme()
      expect(html().getAttribute('data-theme')).toBe(expected)
    })

  it('runs in <head> before the stylesheets and the app, and the page no longer forces the dark theme', () => {
    const head = page.slice(0, page.indexOf('</head>'))
    expect(head).toContain(inline)
    expect(page.indexOf('<script>')).toBeLessThan(page.indexOf('<link rel="stylesheet"') === -1 ? page.indexOf('src/main.tsx') : page.indexOf('<link rel="stylesheet"'))
    expect(page).not.toMatch(/<html[^>]*class="dark"/)
    expect(page).not.toMatch(/background:\s*#/)
  })
})
