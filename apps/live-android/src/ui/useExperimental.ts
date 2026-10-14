/** Experimental features the staff can switch off on the device, without a new release (issue #257). On by default;
 *  the choice is remembered. The storage can be blocked: the switch then lasts for the session. */
import { useCallback, useState } from 'react'

export const EXPERIMENTAL_KEY = 'basketlab-live-experimental'
export type ExperimentalFeature = 'win_prob'

function stored(feature: ExperimentalFeature): boolean {
  try {
    return localStorage.getItem(`${EXPERIMENTAL_KEY}:${feature}`) !== 'off'
  } catch {
    return true
  }
}

export function useExperimental(feature: ExperimentalFeature): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState<boolean>(() => stored(feature))
  const change = useCallback((next: boolean) => {
    setOn(next)
    try { localStorage.setItem(`${EXPERIMENTAL_KEY}:${feature}`, next ? 'on' : 'off') } catch { /* blocked storage: only this session */ }
  }, [feature])
  return [on, change]
}
