import { useEffect, useRef } from 'react'
import { AlertPacer } from './alertPacer'
import type { AlertEntry } from './AlertList'

/**
 * One ``AlertPacer`` for the life of the screen (issue #375): ``onShow`` receives the entries to put on top of the list. When
 * the app goes to the background what is pending is shown at once, and leaving the screen drops the timers.
 */
export function useAlertPacer(onShow: (items: AlertEntry[]) => void, cooldownMs?: number): AlertPacer {
  const show = useRef(onShow)
  show.current = onShow
  const pacer = useRef<AlertPacer | null>(null)
  if (pacer.current === null) pacer.current = new AlertPacer(items => show.current(items), { cooldownMs })
  useEffect(() => {
    const current = pacer.current!
    const onVisibility = () => { if (document.visibilityState === 'hidden') current.flush() }
    document.addEventListener('visibilitychange', onVisibility)
    return () => { document.removeEventListener('visibilitychange', onVisibility); current.clear() }
  }, [])
  return pacer.current
}
