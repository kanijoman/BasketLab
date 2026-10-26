/** Bottom navigation of the app (issue #224): Partido · Boxscore · Partidos · Acerca de. The match keeps the window; the lists live in the others. */
import { Info, Package, Radio, Table2, type LucideIcon } from 'lucide-react'
import { TABS, type TabId } from './useTab'

const ICON: Record<TabId, LucideIcon> = { partido: Radio, boxscore: Table2, paquetes: Package, acerca: Info }

interface Props {
  active: TabId
  onChange: (tab: TabId) => void
}

export default function TabBar({ active, onChange }: Props) {
  return (
    <nav className="tabbar" role="tablist" aria-label="Secciones">
      {TABS.map(({ id, label }) => {
        const Icon = ICON[id]
        return (
          <button key={id} role="tab" id={`tab-${id}`} aria-selected={id === active} aria-controls={`panel-${id}`}
            className={id === active ? 'tab active' : 'tab'} onClick={() => onChange(id)}>
            <Icon size={20} aria-hidden="true" />
            <span>{label}</span>
          </button>
        )
      })}
    </nav>
  )
}
