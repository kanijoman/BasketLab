/**
 * Router config for BasketLab.
 *
 * Route structure:
 *   /                         → HomePage (collection selector)
 *   /:collection              → CollectionHub (dashboard)
 *   /:collection/teams        → TeamStatsPage
 *   /:collection/comparativas → ComparativasPage
 *   /:collection/players      → PlayerStatsPage
 *   /:collection/evolution    → EvolutionPage
 *   /:collection/shots        → ShotChartPage
 *   /:collection/rankings     → RankingsPage
 *   /:collection/report       → ReportPage
 *   /:collection/team-report  → TeamReportPage
 *   /:collection/possessions  → PossessionsPage
 *   /:collection/pbp          → PbpAnalysisPage
 *   /:collection/inout        → InOutPage
 *   /:collection/lineups      → LineupsPage
 *   /:collection/rotaciones   → RotacionesPage
 *   /:collection/conexiones   → ConexionesPage
 *   /:collection/previa       → PreviaPage
 *   /admin                    → redirects to / (the Administration page is gone, #724)
 *
 * AnimatePresence wraps routes for page transition animations.
 */
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { AuthProvider } from '@/context/AuthContext'
import Layout from '@/components/Layout'

// ── Pages ────────────────────────────────────────────────────────────────────
import HomePage from '@/pages/HomePage'
import CollectionHub from '@/pages/CollectionHub'
import TeamStatsPage from '@/pages/TeamStatsPage'
import ComparativasPage from '@/pages/ComparativasPage'
import PlayerStatsPage from '@/pages/PlayerStatsPage'
import LineupsPage from '@/pages/LineupsPage'
import EvolutionPage from '@/pages/EvolutionPage'
import ShotChartPage from '@/pages/ShotChartPage'
import RankingsPage from '@/pages/RankingsPage'
import ReportPage from '@/pages/ReportPage'
import TeamReportPage from '@/pages/TeamReportPage'
import ScoutingRivalPage from '@/pages/ScoutingRivalPage'
import PossessionsPage from '@/pages/PossessionsPage'
import PbpAnalysisPage from '@/pages/PbpAnalysisPage'
import InOutPage from '@/pages/InOutPage'
import MatchAnalysisPage from '@/pages/MatchAnalysisPage'
import MultiPhaseStatsPage from '@/pages/MultiPhaseStatsPage'
import RotacionesPage from '@/pages/RotacionesPage'
import ConexionesPage from '@/pages/ConexionesPage'
import PreviaPage from '@/pages/PreviaPage'
import RequirePublished from '@/components/RequirePublished'
import { NAV_ITEMS } from '@/lib/nav'

/** What the Conexiones page needs from the publication: the menu says it (issue #780), the route asks the same. */
const CONEXIONES_REQUIRES = NAV_ITEMS.find(item => item.subPath === 'conexiones')!.requires!
/** The preview of the match needs the calendar of the competition (#849). */
const PREVIA_REQUIRES = NAV_ITEMS.find(item => item.subPath === 'previa')!.requires!

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
              <Route path="comparativas" element={<ComparativasPage />} />
              <Route path="players"     element={<PlayerStatsPage />} />
              <Route path="evolution"   element={<EvolutionPage />} />
              <Route path="shots"       element={<ShotChartPage />} />
              <Route path="rankings"    element={<RankingsPage />} />
              <Route path="report"      element={<ReportPage />} />
              <Route path="team-report" element={<TeamReportPage />} />
              <Route path="scouting-rival" element={<ScoutingRivalPage />} />
              <Route path="possessions" element={<PossessionsPage />} />
              <Route path="pbp"         element={<PbpAnalysisPage />} />
              <Route path="inout"       element={<InOutPage />} />
              <Route path="lineups"     element={<LineupsPage />} />
              {/* The predictive analysis is out of the web while it is reworked (its page and tabs are kept in pages/PredictivePage.tsx and pages/predictive/): the old address goes to the hub */}
              <Route path="predictive"  element={<Navigate to=".." replace />} />
              <Route path="previa"     element={<RequirePublished requires={PREVIA_REQUIRES}><PreviaPage /></RequirePublished>} />
              <Route path="matches"    element={<MatchAnalysisPage />} />
              <Route path="multiphase"  element={<MultiPhaseStatsPage />} />
              <Route path="rotaciones" element={<RotacionesPage />} />
              <Route path="conexiones" element={<RequirePublished requires={CONEXIONES_REQUIRES}><ConexionesPage /></RequirePublished>} />
            </Route>

            {/* The Administration page is gone (#724: the data is loaded by the scheduled refresh of the archive); its old address goes to the home */}
            <Route path="admin" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AnimatePresence>
    </AuthProvider>
  )
}
