/**
 * Router config for MetricsForAll.
 *
 * Route structure:
 *   /                         → HomePage (collection selector)
 *   /:collection              → CollectionHub (dashboard)
 *   /:collection/teams        → TeamStatsPage
 *   /:collection/players      → PlayerStatsPage
 *   /:collection/evolution    → EvolutionPage
 *   /:collection/shots        → ShotChartPage
 *   /:collection/ai           → AIAnalysisPage
 *   /:collection/rankings     → RankingsPage
 *   /:collection/report       → ReportPage
 *   /:collection/possessions  → PossessionsPage
 *   /:collection/inout        → InOutPage
 *   /:collection/lineups      → LineupsPage
 *   /admin                    → AdminPage (requires admin role)
 *
 * AnimatePresence wraps routes for page transition animations.
 */
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { AuthProvider } from '@/context/AuthContext'
import Layout from '@/components/Layout'
import PrivateRoute from '@/components/PrivateRoute'

// ── Pages ────────────────────────────────────────────────────────────────────
import HomePage from '@/pages/HomePage'
import CollectionHub from '@/pages/CollectionHub'
import TeamStatsPage from '@/pages/TeamStatsPage'
import PlayerStatsPage from '@/pages/PlayerStatsPage'
import LineupsPage from '@/pages/LineupsPage'
import EvolutionPage from '@/pages/EvolutionPage'
import ShotChartPage from '@/pages/ShotChartPage'
import AIAnalysisPage from '@/pages/AIAnalysisPage'
import RankingsPage from '@/pages/RankingsPage'
import ReportPage from '@/pages/ReportPage'
import PossessionsPage from '@/pages/PossessionsPage'
import InOutPage from '@/pages/InOutPage'
import AdminPage from '@/pages/AdminPage'

export default function App() {
  const location = useLocation()

  return (
    <AuthProvider>
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route element={<Layout />}>
            {/* ── Landing ── */}
            <Route index element={<HomePage />} />

            {/* ── Collection workspace ── */}
            <Route path=":collection">
              <Route index element={<CollectionHub />} />
              <Route path="teams"       element={<TeamStatsPage />} />
              <Route path="players"     element={<PlayerStatsPage />} />
              <Route path="evolution"   element={<EvolutionPage />} />
              <Route path="shots"       element={<ShotChartPage />} />
              <Route path="ai"          element={<AIAnalysisPage />} />
              <Route path="rankings"    element={<RankingsPage />} />
              <Route path="report"      element={<ReportPage />} />
              <Route path="possessions" element={<PossessionsPage />} />
              <Route path="inout"       element={<InOutPage />} />
              <Route path="lineups"     element={<LineupsPage />} />
            </Route>

            {/* ── Admin ── */}
            <Route
              path="admin"
              element={
                <PrivateRoute requiredRole="admin">
                  <AdminPage />
                </PrivateRoute>
              }
            />
          </Route>
        </Routes>
      </AnimatePresence>
    </AuthProvider>
  )
}
