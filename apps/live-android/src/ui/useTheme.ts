/** Light, dark or follow the system (issue #322). The tokens already had both themes (`design/tokens.css`: dark by default, light by
 *  `prefers-color-scheme`, and `data-theme` on <html> forces one); this is the way to choose. The choice is remembered on the device and
 *  shared by every control (the header button and Acerca de). The store is the suite's (design/theme.ts, shared with the web since #188);
 *  the app follows the system until the user chooses. */
import { useCallback, useSyncExternalStore } from 'react'
import { createThemeStore, effectiveTheme, type Theme, type ThemePreference } from '../../../../design/theme'

export { effectiveTheme }
export type { Theme, ThemePreference }
export const THEME_KEY = 'basketlab-live-theme'

const store = createThemeStore(THEME_KEY, 'system')

/** Applied before the first paint (main.tsx) so the screen does not flash in the other theme. */
export const applyStoredTheme = store.apply

export function useTheme(): { preference: ThemePreference; theme: Theme; setPreference: (p: ThemePreference) => void; toggle: () => void } {
  const preference = useSyncExternalStore(store.subscribe, store.read, () => 'system' as ThemePreference)
  const theme = effectiveTheme(preference)
  const setPreference = useCallback((p: ThemePreference) => store.set(p), [])
  const toggle = useCallback(() => store.set(effectiveTheme(store.read()) === 'dark' ? 'light' : 'dark'), [])
  return { preference, theme, setPreference, toggle }
}
