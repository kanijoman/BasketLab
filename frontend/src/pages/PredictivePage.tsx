/**
 * PredictivePage — Análisis Predictivo
 *
 * Tabs visible al usuario:
 *   1. Proyección MC           — Monte Carlo simulation for N future games
 *   2. Predicción Partido      — Win/Loss probability
 *   3. Predicción Jugador      — per-player next-game Ridge prediction
 *   4. Clasificación Final     — season-end standings projection
 *
 * Tabs técnicas (Admin > Modelos predictivos):
 *   - Elasticidades            — model training + per-team next-game prediction
 *   - Validación               — walk-forward backtesting metrics
 *
 * Ajuste por Rival (descriptivo) → Estadísticas de Equipo > tab "Aj. Rival"
 */
import { useState } from 'react'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Tabs from '@/components/ui/Tabs'
import { Dices, Target, User, Trophy, type LucideIcon } from 'lucide-react'
import { MonteCarloTab } from './predictive/MonteCarloTab'
import { GamePredictionTab } from './predictive/GamePredictionTab'
import { PlayerPredictionTab } from './predictive/PlayerPredictionTab'
import { SeasonProjectionTab } from './predictive/SeasonProjectionTab'

// The technical tabs live in Admin > Modelos predictivos and are imported from here by AdminPage
export { ElasticityTab } from './predictive/ElasticityTab'
export { ValidationTab } from './predictive/ValidationTab'

type Tab = 'montecarlo' | 'prediction' | 'player' | 'season'

const TABS: Array<{ id: Tab; label: string; icon: LucideIcon }> = [
  { id: 'montecarlo',  label: 'Proyección MC',       icon: Dices },
  { id: 'prediction',  label: 'Predicción Partido',  icon: Target },
  { id: 'player',      label: 'Predicción Jugador',  icon: User },
  { id: 'season',      label: 'Clasificación Final', icon: Trophy },
]

export default function PredictivePage() {
  const [tab, setTab] = useState<Tab>('montecarlo')

  return (
    <PageTransition>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <PageHeader title="Análisis Predictivo"
          subtitle="Estadísticas ajustadas por rival · Modelos Ridge + Bootstrap · Proyección Monte Carlo · Validación walk-forward" />

        <Tabs label="Secciones del análisis predictivo" tabs={TABS} value={tab} onChange={setTab} />

        {/* Tab content */}
        <div className="bg-canvas/50 rounded-xl border border-line/50 p-6">
          {tab === 'montecarlo' && <MonteCarloTab />}
          {tab === 'prediction' && <GamePredictionTab />}
          {tab === 'player'     && <PlayerPredictionTab />}
          {tab === 'season'     && <SeasonProjectionTab />}
        </div>
      </div>
    </PageTransition>
  )
}
