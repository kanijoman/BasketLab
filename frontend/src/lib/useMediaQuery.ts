/** Whether a media query matches now, and again whenever it changes (false outside a browser). */
import { useSyncExternalStore } from 'react'

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    onChange => {
      const media = typeof window !== 'undefined' ? window.matchMedia?.(query) : undefined
      media?.addEventListener?.('change', onChange)
      return () => media?.removeEventListener?.('change', onChange)
    },
    () => (typeof window !== 'undefined' && window.matchMedia?.(query).matches) || false,
    () => false,
  )
}
