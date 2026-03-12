import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import HomePage from '@/pages/HomePage'
import TeamStatsPage from '@/pages/TeamStatsPage'
import PlayerStatsPage from '@/pages/PlayerStatsPage'
import LineupsPage from '@/pages/LineupsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="teams/:collection" element={<TeamStatsPage />} />
        <Route path="players/:collection" element={<PlayerStatsPage />} />
        <Route path="lineups/:collection" element={<LineupsPage />} />
      </Route>
    </Routes>
  )
}
