/**
 * Application shell.
 *
 * Structure:
 *   ┌──────────────────────────────────────────┐
 *   │  Header (fixed, full-width)              │
 *   ├──────────┬───────────────────────────────┤
 *   │ Sidebar  │  <Outlet /> (page content)    │
 *   │(optional)│                               │
 *   └──────────┴───────────────────────────────┘
 *
 * The sidebar is only visible when a collection is active (URL has /:collection).
 */
import { Component, useState, type ReactNode } from 'react'
import { Outlet, Link, useParams } from 'react-router-dom'
import { ChevronRight, Home, ExternalLink, Menu } from 'lucide-react'
import Sidebar, { MobileNav } from '@/components/Sidebar'
import CollectionSwitcher from '@/components/CollectionSwitcher'
import { IconButton } from '@/components/ui/Button'
import { useMediaQuery } from '@/lib/useMediaQuery'
import ThemeControl from '@/components/ThemeControl'
import { localDataEnabled, localDatasets } from '@/datasource/switch'
import BrandLogo from '@/components/BrandLogo'
import { useCollection, CollectionProvider } from '@/context/CollectionContext'

class PageErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  componentDidCatch(error: Error) { console.error('[PageErrorBoundary]', error) }
  render() {
    if (this.state.error) return (
      <div className="p-8 space-y-2">
        <p className="text-bad font-semibold">Error al cargar la página</p>
        <pre className="text-xs text-ink-muted whitespace-pre-wrap">{(this.state.error as Error).message}</pre>
      </div>
    )
    return this.props.children
  }
}

const PHONE = '(max-width: 767px)'

function Header({ onOpenMenu }: { onOpenMenu?: () => void }) {
  const { collection } = useCollection()

  return (
    <header className="h-14 bg-surface border-b border-line flex items-center px-3 sm:px-4 gap-2 sm:gap-4 shrink-0 z-20">
      {/* Menu of the phone (the sidebar is not fixed there, issue #191) */}
      {onOpenMenu && (
        <IconButton icon={Menu} label="Abrir menú" onClick={onOpenMenu} className="-ml-1 shrink-0" />
      )}

      {/* Logo */}
      <Link to="/" aria-label="BasketLab — inicio" className="shrink-0 rounded-md transition-opacity hover:opacity-80">
        <BrandLogo nameClassName="hidden sm:inline" />
      </Link>

      {/* Breadcrumb */}
      {collection && (
        <nav aria-label="Ruta" className="flex items-center gap-1 text-xs text-ink-muted min-w-0">
          <Link to="/" className="hover:text-ink transition-colors" aria-label="Inicio">
            <Home className="w-3.5 h-3.5" />
          </Link>
          <ChevronRight className="w-3 h-3 opacity-40 shrink-0" />
          <span className="text-ink font-medium truncate hidden md:inline">{collection.label}</span>
          <span className="ml-1 px-1.5 py-0.5 bg-line/60 rounded text-ink-faint shrink-0">
            {collection.isFbcyl ? 'FBCYL' : 'FEB'}
          </span>
        </nav>
      )}
      {collection && <div className="min-w-0 hidden md:block"><CollectionSwitcher /></div>}

      {/* Right side — future: user avatar / auth */}
      <div className="ml-auto flex items-center gap-2">
        {localDataEnabled() && (
          <span className="px-1.5 py-0.5 rounded bg-accent/20 text-accent-text text-xs"
                title={`Se leen de los ficheros publicados, no de la API: ${localDatasets().join(', ')} (?data=api para volver a la API)`}>Datos locales</span>
        )}
        <ThemeControl />
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="btn-ghost text-xs hidden md:inline-flex"
        >
          API <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </header>
  )
}

function Shell() {
  const { collection: collectionParam } = useParams<{ collection?: string }>()
  const hasCollection = Boolean(collectionParam)
  const phone = useMediaQuery(PHONE)
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex flex-col h-full">
      <a href="#contenido" className="sr-only rounded-lg bg-surface px-3 py-2 text-sm font-medium text-ink shadow-panel focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50">Saltar al contenido</a>
      <Header onOpenMenu={hasCollection && phone ? () => setMenuOpen(true) : undefined} />

      <div className="flex flex-1 min-h-0">
        {/* Sidebar — only inside a collection; on a phone it is the menu over the page */}
        {hasCollection && !phone && <Sidebar />}
        {hasCollection && phone && <MobileNav open={menuOpen} onClose={() => setMenuOpen(false)} />}

        {/* Page content */}
        <main id="contenido" tabIndex={-1} className="flex-1 min-w-0 overflow-y-auto focus:outline-none">
          <div className="p-3 sm:p-5 max-w-[1600px] mx-auto min-h-full">
            <PageErrorBoundary>
              <Outlet />
            </PageErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}

/**
 * Layout wraps Shell in CollectionProvider so the context can read
 * the :collection URL param from inside a nested route.
 */
export default function Layout() {
  return (
    <CollectionProvider>
      <Shell />
    </CollectionProvider>
  )
}
