/**
 * BasketLab Talent (epic #872): search, profiling and fit of players of any age and competition.
 *
 * Routes (the pages come with B2–B5):
 *   /                     → the search of players (B3 #879); it also says when no data is published yet
 *   /jugador/:personId    → the profile of a player (B4 #880)
 *   /comparar?j=a,b,c     → the comparator of two or three players (B5 #881)
 * The header has the main navigation (Buscar · Comparar · Mi equipo, #1007, #882).
 *   /mi-equipo?c=&e=       → the squad of a team, its holes and the searches that would fill them (C1 #882)
 *   *   → /
 */
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import talentMark from '@design/brand/talent-mark.svg'
import BrandLogo from '@/components/BrandLogo'
import ThemeControl from '@/components/ThemeControl'
import ComparePage from './ComparePage'
import MyTeamPage from './MyTeamPage'
import { compareHref } from './compareMemory'
import PlayerPage from './PlayerPage'
import SearchPage from './SearchPage'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${isActive ? 'bg-accent/10 text-accent-text' : 'text-ink-muted hover:bg-surface-raised hover:text-ink'}`

/** The main navigation (#1007): the search and the comparator, the one you are in marked (`aria-current`). The comparator link carries the comparison that was left. */
function MainNav({ className = '' }: { className?: string }) {
  useLocation()                          // the remembered comparison changes with the pages you visit: the link is read again on each one
  return (
    <nav aria-label="Principal" className={`flex items-center gap-1 ${className}`}>
      <NavLink to="/" end className={linkClass}>Buscar</NavLink>
      <NavLink to={compareHref()} className={linkClass}>Comparar</NavLink>
      <NavLink to="/mi-equipo" className={linkClass}>Mi equipo</NavLink>
    </nav>
  )
}

export default function MarketApp() {
  return (
    <div className="flex h-full flex-col">
      <a href="#contenido" className="sr-only rounded-lg bg-surface px-3 py-2 text-sm font-medium text-ink shadow-panel focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50">Saltar al contenido</a>
      {/* on a phone the navigation goes under the brand (it does not fit beside it at 320 px); from `sm` it sits beside it */}
      <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line bg-surface px-4 py-2">
        <BrandLogo product="Talent" markSrc={talentMark} />
        <MainNav className="order-3 w-full sm:order-2 sm:ml-3 sm:w-auto" />
        <div className="order-2 ml-auto sm:order-3"><ThemeControl /></div>
      </header>
      <main id="contenido" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto focus:outline-none">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/jugador/:personId" element={<PlayerPage />} />
          <Route path="/comparar" element={<ComparePage />} />
          <Route path="/mi-equipo" element={<MyTeamPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
