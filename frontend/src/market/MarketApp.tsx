/**
 * BasketLab Talent (epic #872): search, profiling and fit of players of any age and competition.
 *
 * Routes (the pages come with B2–B5):
 *   /   → home: what the product is and whether the market data is published
 *   *   → /
 */
import { Navigate, Route, Routes } from 'react-router-dom'
import { Search } from 'lucide-react'
import talentMark from '@design/brand/talent-mark.svg'
import BrandLogo from '@/components/BrandLogo'
import ThemeControl from '@/components/ThemeControl'
import EmptyState from '@/components/ui/EmptyState'
import PageHeader from '@/components/ui/PageHeader'

function Home() {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-4 sm:p-6">
      <PageHeader title="BasketLab Talent" subtitle="Búsqueda, perfilado y encaje de jugadores y jugadoras de cualquier edad y competición" />
      <EmptyState
        icon={Search}
        title="Aún no hay datos de jugadores publicados"
        description="El buscador aparece aquí en cuanto se publique el primer conjunto de datos."
      />
    </div>
  )
}

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
          <Route path="/" element={<Home />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
