/** Which severities the staff has hidden in the alert flow (issue #322), remembered on the device. The storage can be blocked: the
 *  filter then lasts for the session. */
import { useCallback, useState } from 'react'
import type { Alert } from '../engine/types'

export const FILTER_KEY = 'basketlab-live-alert-filter'
type Severity = Alert['severity']
const SEVERITIES: Severity[] = ['critical', 'warning', 'info']

function stored(): Set<Severity> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(FILTER_KEY) ?? '[]')
    return new Set(Array.isArray(parsed) ? parsed.filter((s): s is Severity => SEVERITIES.includes(s as Severity)) : [])
  } catch {
    return new Set()
  }
}

export function useAlertFilter(): { hidden: Set<Severity>; toggle: (severity: Severity) => void } {
  const [hidden, setHidden] = useState<Set<Severity>>(stored)
  const toggle = useCallback((severity: Severity) => {
    setHidden(prev => {
      const next = new Set(prev)
      if (next.has(severity)) next.delete(severity)
      else next.add(severity)
      try { localStorage.setItem(FILTER_KEY, JSON.stringify([...next])) } catch { /* blocked storage: only this session */ }
      return next
    })
  }, [])
  return { hidden, toggle }
}
