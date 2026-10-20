/** The active tab of the app, remembered between sessions (issue #224). The storage can be blocked: it then just does not remember. */
import { useCallback, useState } from 'react'

export type TabId = 'partido' | 'paquetes' | 'acerca'
export const TABS: { id: TabId; label: string }[] = [
  { id: 'partido', label: 'Partido' },
  { id: 'paquetes', label: 'Partidos' },
  { id: 'acerca', label: 'Acerca de' },
]
export const TAB_KEY = 'basketlab-live-tab'

const isTab = (value: unknown): value is TabId => TABS.some(t => t.id === value)

function stored(): TabId {
  try {
    const value = localStorage.getItem(TAB_KEY)
    return isTab(value) ? value : 'partido'
  } catch {
    return 'partido'
  }
}

export function useTab(): [TabId, (tab: TabId) => void] {
  const [tab, setTab] = useState<TabId>(stored)
  const change = useCallback((next: TabId) => {
    setTab(next)
    try { localStorage.setItem(TAB_KEY, next) } catch { /* private mode or blocked storage: it is only a convenience */ }
  }, [])
  return [tab, change]
}
