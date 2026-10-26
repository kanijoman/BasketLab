/** The active tab of the app. It always opens on the list of matches (Partidos): the match tab is for the one already chosen (demo, recording, finished or live). */
import { useCallback, useState } from 'react'

export type TabId = 'partido' | 'boxscore' | 'paquetes' | 'acerca'
export const TABS: { id: TabId; label: string }[] = [
  { id: 'partido', label: 'Partido' },
  { id: 'boxscore', label: 'Boxscore' },
  { id: 'paquetes', label: 'Partidos' },
  { id: 'acerca', label: 'Acerca de' },
]

export function useTab(initial: TabId = 'paquetes'): [TabId, (tab: TabId) => void] {
  const [tab, setTab] = useState<TabId>(initial)
  const change = useCallback((next: TabId) => setTab(next), [])
  return [tab, change]
}
