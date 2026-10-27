/**
 * Light, dark or the system's: the theme store of the suite (issues #322, #188), shared by the live app and the web. No framework: each app wraps it
 * in its own hook (`useSyncExternalStore`). design/tokens.css already has both themes (dark by default, light by `prefers-color-scheme`, and
 * `data-theme` on <html> forces one); this only chooses. The choice is remembered on the device; when the storage is blocked it lasts for the session.
 */
export type ThemePreference = 'system' | 'light' | 'dark'
export type Theme = 'light' | 'dark'

/** `--bg` of each theme in tokens.css, for the browser bar (`<meta name="theme-color">`). */
export const THEME_COLOR: Record<Theme, string> = { dark: '#0d1117', light: '#f6f8fa' }

export interface ThemeStore {
  read(): ThemePreference
  set(preference: ThemePreference): void
  /** Put the stored choice on <html>: before the first paint, and after every change. */
  apply(): void
  subscribe(onChange: () => void): () => void
}

const valid = (value: unknown): value is ThemePreference => value === 'system' || value === 'light' || value === 'dark'

export function effectiveTheme(preference: ThemePreference): Theme {
  if (preference !== 'system') return preference
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

/** One store per app: `key` in localStorage and the theme it opens with until the user chooses (`fallback`). */
export function createThemeStore(key: string, fallback: ThemePreference): ThemeStore {
  const listeners = new Set<() => void>()
  let memory: ThemePreference | null = null               // what was chosen when the storage cannot hold it

  function read(): ThemePreference {
    try {
      const value = localStorage.getItem(key)
      return valid(value) ? value : fallback
    } catch {
      return memory ?? fallback
    }
  }

  function apply(): void {
    const preference = read()
    const root = document.documentElement
    if (preference === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', preference)
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[effectiveTheme(preference)])
  }

  function set(preference: ThemePreference): void {
    memory = preference
    try { localStorage.setItem(key, preference) } catch { /* blocked storage: only this session */ }
    apply()
    listeners.forEach(notify => notify())
  }

  function subscribe(onChange: () => void): () => void {
    listeners.add(onChange)
    const media = typeof window !== 'undefined' ? window.matchMedia?.('(prefers-color-scheme: light)') : undefined
    media?.addEventListener?.('change', onChange)
    return () => { listeners.delete(onChange); media?.removeEventListener?.('change', onChange) }
  }

  return { read, set, apply, subscribe }
}
