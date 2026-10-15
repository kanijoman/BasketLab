/** Light, dark or follow the system (issue #322). The tokens already had both themes (`design/tokens.css`: dark by default, light by
 *  `prefers-color-scheme`, and `data-theme` on <html> forces one); this is the way to choose. The choice is remembered on the device and
 *  shared by every control (the header button and Acerca de) through one small store. The storage can be blocked: then it lasts for the session. */
import { useCallback, useSyncExternalStore } from 'react'

export const THEME_KEY = 'basketlab-live-theme'
export type ThemePreference = 'system' | 'light' | 'dark'
export type Theme = 'light' | 'dark'

const THEME_COLOR: Record<Theme, string> = { dark: '#0d1117', light: '#f6f8fa' }
const listeners = new Set<() => void>()
let memory: ThemePreference | null = null    // what was chosen when the storage cannot hold it

const valid = (value: unknown): value is ThemePreference => value === 'system' || value === 'light' || value === 'dark'

function readPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_KEY)
    return valid(value) ? value : 'system'
  } catch {
    return memory ?? 'system'
  }
}

export function effectiveTheme(preference: ThemePreference): Theme {
  if (preference !== 'system') return preference
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function apply(preference: ThemePreference): void {
  const root = document.documentElement
  if (preference === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', preference)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[effectiveTheme(preference)])
}

/** Applied before the first paint (main.tsx) so the screen does not flash in the other theme. */
export function applyStoredTheme(): void {
  apply(readPreference())
}

function setPreference(preference: ThemePreference): void {
  memory = preference
  try { localStorage.setItem(THEME_KEY, preference) } catch { /* blocked storage: only this session */ }
  apply(preference)
  listeners.forEach(notify => notify())
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange)
  const media = typeof window !== 'undefined' ? window.matchMedia?.('(prefers-color-scheme: light)') : undefined
  media?.addEventListener?.('change', onChange)
  return () => { listeners.delete(onChange); media?.removeEventListener?.('change', onChange) }
}

export function useTheme(): { preference: ThemePreference; theme: Theme; setPreference: (p: ThemePreference) => void; toggle: () => void } {
  const preference = useSyncExternalStore(subscribe, readPreference, () => 'system' as ThemePreference)
  const theme = effectiveTheme(preference)
  const toggle = useCallback(() => setPreference(effectiveTheme(readPreference()) === 'dark' ? 'light' : 'dark'), [])
  return { preference, theme, setPreference, toggle }
}
