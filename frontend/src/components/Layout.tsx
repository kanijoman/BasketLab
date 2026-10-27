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
import { Component, type ReactNode } from 'react'
import { Outlet, Link, useParams, useNavigate } from 'react-router-dom'
import { ChevronRight, Home, ExternalLink } from 'lucide-react'
import Sidebar from '@/components/Sidebar'
import ThemeControl from '@/components/ThemeControl'
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

function Header() {
  const { collection } = useCollection()
  const navigate = useNavigate()

  return (
    <header className="h-14 bg-surface border-b border-line flex items-center px-4 gap-4 shrink-0 z-20">
      {/* Logo */}
      <Link
        to="/"
        className="flex items-center gap-2 font-bold text-accent-text hover:text-accent-text transition-colors shrink-0"
      >
        <img src="/logo.png" alt="BasketLab" className="h-7 w-7 rounded" onError={e => { (e.target as HTMLImageElement).style.display='none' }} />
        <span className="text-sm tracking-tight hidden sm:block">BasketLab</span>
      </Link>

      {/* Breadcrumb */}
      {collection && (
        <nav className="flex items-center gap-1 text-xs text-ink-muted min-w-0">
          <button
            onClick={() => navigate('/')}
            className="hover:text-ink transition-colors"
            aria-label="Inicio"
          >
            <Home className="w-3.5 h-3.5" />
          </button>
          <ChevronRight className="w-3 h-3 opacity-40 shrink-0" />
          <span className="text-ink font-medium truncate">{collection.label}</span>
          <span className="ml-1 px-1.5 py-0.5 bg-line/60 rounded text-ink-faint shrink-0">
            {collection.isFbcyl ? 'FBCYL' : 'FEB'}
          </span>
        </nav>
      )}

      {/* Right side — future: user avatar / auth */}
      <div className="ml-auto flex items-center gap-2">
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

  return (
    <div className="flex flex-col h-full">
      <Header />

      <div className="flex flex-1 min-h-0">
        {/* Sidebar — only when inside a collection */}
        {hasCollection && <Sidebar />}

        {/* Page content */}
        <main className="flex-1 min-w-0 overflow-y-auto">
          <div className="p-5 max-w-[1600px] mx-auto min-h-full">
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
