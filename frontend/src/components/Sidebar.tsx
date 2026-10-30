/**
 * Navigation of a collection (issue #191, U4), from lib/nav.ts: the pages in groups (Equipos, Jugadores, Partido, Live, Informes).
 *
 * - `Sidebar`: the fixed column on a wide screen; collapsed it shows only icons (remembered in localStorage).
 * - `MobileNav`: the same links as a menu over the page on a phone (modal dialog: Escape, backdrop and its button close it, the focus goes inside).
 */
import { useEffect, useRef, useState } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Settings, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { IconButton } from '@/components/ui/Button'
import { NAV_GROUPS, SUMMARY, type NavItem } from '@/lib/nav'

const STORAGE_KEY = 'sidebar-collapsed'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
    'focus-visible:ring-2 focus-visible:ring-focus',
    isActive ? 'bg-accent/20 text-accent-text border border-accent/30' : 'text-ink-muted hover:bg-surface-raised hover:text-ink',
  )

/** The groups of links; `compact` is the icons-only column, `onNavigate` lets the menu of the phone close itself. */
function NavList({ base, compact = false, onNavigate }: { base: string; compact?: boolean; onNavigate?: () => void }) {
  const link = (item: NavItem) => (
    <NavLink
      key={item.subPath}
      to={item.subPath ? `${base}/${item.subPath}` : base}
      end={item.subPath === ''}
      className={linkClass}
      title={compact ? item.label : undefined}
      onClick={onNavigate}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {!compact && <span className="truncate">{item.label}</span>}
    </NavLink>
  )
  return (
    <nav aria-label="Páginas de la competición" className="flex-1 space-y-3 overflow-y-auto overflow-x-hidden px-2 py-3">
      <div>{link(SUMMARY)}</div>
      {NAV_GROUPS.map(group => (
        <div key={group.label} className="space-y-0.5">
          {compact
            ? <div className="mx-2 border-t border-line" aria-hidden="true" />
            : <h2 className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-ink-faint">{group.label}</h2>}
          {group.items.map(link)}
        </div>
      ))}
      <div className="space-y-0.5 border-t border-line pt-3">
        <NavLink to="/admin" className={linkClass} title={compact ? 'Administración' : undefined} onClick={onNavigate}>
          <Settings className="h-4 w-4 shrink-0" />
          {!compact && <span className="truncate">Administración</span>}
        </NavLink>
      </div>
    </nav>
  )
}

export default function Sidebar() {
  const { collection } = useParams<{ collection?: string }>()
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) === 'true' } catch { return false }
  })

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, String(collapsed)) } catch { /* ignore */ }
  }, [collapsed])

  if (!collection) return null

  return (
    <aside className={cn('flex h-full flex-col overflow-hidden border-r border-line bg-surface transition-[width] duration-200 ease-in-out', collapsed ? 'w-14' : 'w-56')}>
      <NavList base={`/${encodeURIComponent(collection)}`} compact={collapsed} />
      <div className="border-t border-line px-2 pb-3 pt-2">
        <IconButton icon={collapsed ? ChevronRight : ChevronLeft} label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
          onClick={() => setCollapsed(c => !c)} className="w-full justify-center px-3 py-2" />
      </div>
    </aside>
  )
}

/** The navigation as a menu over the page, for a phone. */
export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { collection } = useParams<{ collection?: string }>()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    panel.current?.querySelector<HTMLElement>('a, button')?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open || !collection) return null

  return (
    <div className="fixed inset-0 z-40 flex">
      <div data-testid="nav-backdrop" className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden="true" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label="Menú de navegación"
        className="relative flex h-full w-72 max-w-[85vw] flex-col bg-surface shadow-panel"
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <span className="text-sm font-semibold text-ink">Menú</span>
          <IconButton icon={X} label="Cerrar menú" onClick={onClose} />
        </div>
        <NavList base={`/${encodeURIComponent(collection)}`} onNavigate={onClose} />
      </div>
    </div>
  )
}
