/**
 * BasketLab Talent (epic #872): search, profiling and fit of players of any age and competition.
 *
 * Routes (the pages come with B2–B5):
 *   /   → the search of players (B3 #879); it also says when no data is published yet
 *   *   → /
 */
import { Navigate, Route, Routes } from 'react-router-dom'
import talentMark from '@design/brand/talent-mark.svg'
import BrandLogo from '@/components/BrandLogo'
import ThemeControl from '@/components/ThemeControl'
import SearchPage from './SearchPage'

export default function MarketApp() {
  return (
    <div className="flex h-full flex-col">
      <a href="#contenido" className="sr-only rounded-lg bg-surface px-3 py-2 text-sm font-medium text-ink shadow-panel focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50">Saltar al contenido</a>
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-2">
        <BrandLogo product="Talent" markSrc={talentMark} />
        <ThemeControl />
      </header>
      <main id="contenido" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto focus:outline-none">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
