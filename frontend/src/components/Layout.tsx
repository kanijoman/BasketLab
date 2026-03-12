import { Outlet, NavLink } from 'react-router-dom'

/**
 * Application shell — top nav bar + main content area.
 * All page routes are rendered inside <Outlet />.
 */
export default function Layout() {
  const navClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-2 rounded text-sm font-medium transition-colors ${
      isActive
        ? 'bg-primary-600 text-white'
        : 'text-gray-300 hover:bg-court-800 hover:text-white'
    }`

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top nav ── */}
      <header className="bg-court-950 text-white shadow-lg">
        <div className="max-w-screen-xl mx-auto px-4 flex items-center h-14 gap-6">
          <span className="font-bold text-primary-500 text-lg tracking-tight">
            🏀 MetricsForAll
          </span>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navClass}>
              Inicio
            </NavLink>
          </nav>
        </div>
      </header>

      {/* ── Page content ── */}
      <main className="flex-1 max-w-screen-xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>

      <footer className="bg-court-950 text-gray-500 text-xs text-center py-3">
        MetricsForAll &copy; {new Date().getFullYear()} — FEB / FBCYL
      </footer>
    </div>
  )
}
