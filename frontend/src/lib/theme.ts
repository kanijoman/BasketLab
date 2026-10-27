/**
 * Theme of the web (issue #188): light by default (decision of 27/10/2026), dark, or the device's. The store is the one of the live app
 * (design/theme.ts); index.html repeats THEME_KEY and DEFAULT_THEME in its first script, so the page paints in its theme from the start.
 */
import { useCallback, useSyncExternalStore } from 'react'
import { createThemeStore, effectiveTheme, type Theme, type ThemePreference } from '@design/theme'

export type { Theme, ThemePreference }
export const THEME_KEY = 'basketlab-web-theme'
export const DEFAULT_THEME: ThemePreference = 'light'

const store = createThemeStore(THEME_KEY, DEFAULT_THEME)

/** Called by main.tsx before the first render (index.html already did it; this also sets the colour of the browser bar). */
export const applyStoredTheme = store.apply

export function useTheme(): { preference: ThemePreference; theme: Theme; setPreference: (p: ThemePreference) => void } {
  const preference = useSyncExternalStore(store.subscribe, store.read, () => DEFAULT_THEME)
  const setPreference = useCallback((p: ThemePreference) => store.set(p), [])
  return { preference, theme: effectiveTheme(preference), setPreference }
}
