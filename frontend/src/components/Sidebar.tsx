/**
 * Sidebar — collapsible left navigation for the collection workspace.
 *
 * When collapsed it shows only icons; when expanded it shows icon + label.
 * The collapse state is persisted in localStorage.
 */
import { useState, useEffect } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import {
  BarChart2,
  Users,
  TrendingUp,
  Target,
  Bot,
  Trophy,
  FileText,
  Activity,
  ArrowLeftRight,
  Users2,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Settings,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavItem {
  icon: React.ComponentType<{ className?: string }>
  label: string
  subPath: string
  /** Future: role required for this item */
  // role?: UserRole
}

const NAV_ITEMS: NavItem[] = [
  { icon: LayoutDashboard,  label: 'Resumen',              subPath: '' },
  { icon: BarChart2,        label: 'Equipo',               subPath: 'teams' },
  { icon: Users,            label: 'Individual',           subPath: 'players' },
  { icon: TrendingUp,       label: 'Evolución',            subPath: 'evolution' },
  { icon: Target,           label: 'Gráficos de tiro',     subPath: 'shots' },
  { icon: Bot,              label: 'Análisis IA',          subPath: 'ai' },
  { icon: Trophy,           label: 'Rankings',             subPath: 'rankings' },
  { icon: FileText,         label: 'Informe semanal',      subPath: 'report' },
  { icon: Activity,         label: 'Posesiones',           subPath: 'possessions' },
  { icon: ArrowLeftRight,   label: 'IN/OUT',               subPath: 'inout' },
  { icon: Users2,           label: 'Combinaciones',        subPath: 'lineups' },
  { icon: BrainCircuit,     label: 'Análisis Predictivo', subPath: 'predictive' },
]

const STORAGE_KEY = 'sidebar-collapsed'

export default function Sidebar() {
  const { collection } = useParams<{ collection?: string }>()
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === 'true' } catch { return false }
  })

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, String(collapsed)) } catch { /* ignore */ }
  }, [collapsed])

  if (!collection) return null

  const base = `/${encodeURIComponent(collection)}`

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
      'focus-visible:ring-2 focus-visible:ring-brand-500',
      isActive
        ? 'bg-brand-600/20 text-brand-400 border border-brand-600/30'
        : 'text-ink-secondary hover:bg-surface-hover hover:text-ink-primary',
    )

  return (
    <aside
      className={cn(
        'flex flex-col h-full bg-surface-raised border-r border-surface-border',
        'transition-[width] duration-200 ease-in-out overflow-hidden',
        collapsed ? 'w-14' : 'w-56',
      )}
    >
      {/* Nav items */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto overflow-x-hidden">
        {NAV_ITEMS.map(({ icon: Icon, label, subPath }) => (
          <NavLink
            key={subPath}
            to={subPath ? `${base}/${subPath}` : base}
            end={subPath === ''}
            className={linkClass}
            title={collapsed ? label : undefined}
          >
            <Icon className="w-4 h-4 shrink-0" />
            {!collapsed && (
              <span className="truncate">{label}</span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Admin link + collapse toggle */}
      <div className="px-2 pb-3 space-y-0.5 border-t border-surface-border pt-3">
        <NavLink
          to="/admin"
          className={linkClass}
          title={collapsed ? 'Administración' : undefined}
        >
          <Settings className="w-4 h-4 shrink-0" />
          {!collapsed && <span className="truncate">Administración</span>}
        </NavLink>

        <button
          onClick={() => setCollapsed(c => !c)}
          className="w-full flex items-center justify-center px-3 py-2 rounded-lg
                     text-ink-muted hover:text-ink-secondary hover:bg-surface-hover
                     transition-colors"
          title={collapsed ? 'Expandir menú' : 'Colapsar menú'}
        >
          {collapsed
            ? <ChevronRight className="w-4 h-4" />
            : <ChevronLeft className="w-4 h-4" />
          }
        </button>
      </div>
    </aside>
  )
}
