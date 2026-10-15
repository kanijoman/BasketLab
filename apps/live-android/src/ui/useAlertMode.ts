/** How many alerts the staff wants (issue #130): aggressive, medium (the default) or conservative. It is not a set of thresholds: the engine
 *  maps each mode to values we calibrate (src/live_core/modes.py). The choice is remembered; the storage can be blocked: then it lasts the session. */
import { useCallback, useState } from 'react'

export const ALERT_MODE_KEY = 'basketlab-live-alert-mode'
export type AlertMode = 'aggressive' | 'medium' | 'conservative'

export const ALERT_MODES: { id: AlertMode; label: string; help: string }[] = [
  { id: 'aggressive', label: 'Agresivo', help: 'Más avisos y antes: fatiga, parciales, rachas y cambios de la probabilidad se avisan con menos margen.' },
  { id: 'medium', label: 'Medio', help: 'El equilibrio de serie.' },
  { id: 'conservative', label: 'Conservador', help: 'Solo lo que está claro: menos avisos, los parciales y los cambios grandes.' },
]

function stored(): AlertMode {
  try {
    const value = localStorage.getItem(ALERT_MODE_KEY)
    return ALERT_MODES.some(m => m.id === value) ? (value as AlertMode) : 'medium'
  } catch {
    return 'medium'
  }
}

export function useAlertMode(): [AlertMode, (mode: AlertMode) => void] {
  const [mode, setMode] = useState<AlertMode>(stored)
  const change = useCallback((next: AlertMode) => {
    setMode(next)
    try { localStorage.setItem(ALERT_MODE_KEY, next) } catch { /* blocked storage: only this session */ }
  }, [])
  return [mode, change]
}
