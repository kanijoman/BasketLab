/**
 * CollectionHub — dashboard overview for a loaded collection.
 *
 * Shows key highlights (top scorer, best OER, best record, pace)
 * and a quick-access grid to all analysis modules.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart2, Users, TrendingUp, Target, Bot, Trophy,
  FileText, Activity, ArrowLeftRight, Users2, Loader2, BrainCircuit,
} from 'lucide-react'
import { useCollection } from '@/context/CollectionContext'
import { getTeamStats, getPlayerStats, type TeamStat, type PlayerStat } from '@/api/client'
import StatCard from '@/components/ui/StatCard'
import PageTransition from '@/components/ui/PageTransition'
import { fmt } from '@/lib/utils'

// ── Module card definition ────────────────────────────────────────────────────
interface Module {
  icon: React.ComponentType<{ className?: string }>
  label: string
  description: string
  subPath: string
  accent: string
}

const MODULES: Module[] = [
  { icon: BarChart2,      label: 'Estadísticas de Equipo',     description: 'Básicas y avanzadas con cuartiles y tendencias',  subPath: 'teams',       accent: 'text-brand-400' },
  { icon: Users,          label: 'Estadísticas Individuales',  description: 'Jugadores con radar, comparativa y trends',        subPath: 'players',     accent: 'text-brand-400' },
  { icon: TrendingUp,     label: 'Evolución Temporal',         description: 'Progresión de métricas a lo largo de la temporada', subPath: 'evolution',   accent: 'text-accent-400' },
  { icon: Target,         label: 'Gráficos de Tiro',           description: 'Mapa de calor FIBA interactivo por zonas',         subPath: 'shots',       accent: 'text-accent-400' },
  { icon: Bot,            label: 'Análisis IA',                description: 'Scouting y análisis con Gemini / OpenAI / Groq',   subPath: 'ai',          accent: 'text-warn' },
  { icon: Trophy,         label: 'Rankings',                   description: 'Clasificación de jugadores por cualquier métrica', subPath: 'rankings',    accent: 'text-warn' },
  { icon: Activity,       label: 'Posesiones',                 description: 'Ritmo, OER/DER y análisis de posesiones',          subPath: 'possessions', accent: 'text-accent-400' },
  { icon: ArrowLeftRight, label: 'IN/OUT',                     description: 'Impacto por jugador dentro/fuera de la cancha',    subPath: 'inout',       accent: 'text-brand-400' },
  { icon: Users2,         label: 'Combinaciones',              description: 'Mejores y peores combinaciones de jugadores por estadística',    subPath: 'lineups',     accent: 'text-brand-400' },
  { icon: FileText,       label: 'Informe Semanal',            description: 'Report builder con PDF/DOCX exportable',           subPath: 'report',      accent: 'text-warn' },
  { icon: BrainCircuit,   label: 'Análisis Predictivo',        description: 'Elasticidades Ridge · Monte Carlo · Predicción partido',   subPath: 'predictive',  accent: 'text-brand-400' },
]

// ── Highlights derived from data ──────────────────────────────────────────────
interface Highlights {
  topScorer: { name: string; ppg: number } | null
  bestOER: { team: string; oer: number } | null
  avgPace: number | null
  totalTeams: number
  totalPlayers: number
}

function deriveHighlights(teams: TeamStat[], players: PlayerStat[]): Highlights {
  const sorted = [...teams].sort((a, b) => (b.offensive_rating ?? 0) - (a.offensive_rating ?? 0))
  const topPlayer = [...players].sort((a, b) => b.points_per_game - a.points_per_game)[0]
  const avgPace = teams.length
    ? teams.reduce((s, t) => s + (t.possessions_per_game ?? 0), 0) / teams.length
    : null

  return {
    topScorer: topPlayer ? { name: topPlayer.player_name, ppg: topPlayer.points_per_game } : null,
    bestOER: sorted[0]?.offensive_rating ? { team: sorted[0].team_name, oer: sorted[0].offensive_rating } : null,
    avgPace: avgPace && avgPace > 0 ? avgPace : null,
    totalTeams: teams.length,
    totalPlayers: players.length,
  }
}

export default function CollectionHub() {
  const { collection, navigateTo } = useCollection()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [highlights, setHighlights] = useState<Highlights | null>(null)

  useEffect(() => {
    if (!collection) return
    setLoading(true)
    Promise.all([
      getTeamStats(collection.name),
      getPlayerStats(collection.name),
    ])
      .then(([teamData, playerData]) => {
        setHighlights(deriveHighlights(teamData.team_stats, playerData))
      })
      .catch(() => setHighlights(null))
      .finally(() => setLoading(false))
  }, [collection?.name])

  const goTo = (subPath: string) => navigateTo(subPath)

  if (!collection) {
    return (
      <div className="flex items-center justify-center h-64">
        <button className="btn-primary" onClick={() => navigate('/')}>
          Seleccionar colección
        </button>
      </div>
    )
  }

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Title */}
        <div>
          <h1 className="text-2xl font-bold text-ink-primary">{collection.label}</h1>
          <p className="text-ink-secondary text-sm mt-1">
            {collection.isFbcyl ? 'FBCYL — Castilla y León' : 'FEB — Liga Nacional'}
          </p>
        </div>

        {/* Highlight stats */}
        {loading ? (
          <div className="flex items-center gap-2 text-ink-secondary text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            Cargando datos…
          </div>
        ) : highlights && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {highlights.topScorer && (
              <StatCard
                label="Máx. anotador"
                value={fmt(highlights.topScorer.ppg)}
                sub={highlights.topScorer.name}
                accent="green"
                onClick={() => goTo('rankings')}
              />
            )}
            {highlights.bestOER && (
              <StatCard
                label="Mejor OER"
                value={fmt(highlights.bestOER.oer)}
                sub={highlights.bestOER.team}
                accent="blue"
                onClick={() => goTo('teams')}
              />
            )}
            {highlights.avgPace && (
              <StatCard
                label="Ritmo medio"
                value={fmt(highlights.avgPace)}
                sub="posesiones / partido"
                accent="default"
                onClick={() => goTo('possessions')}
              />
            )}
            <StatCard
              label="Equipos"
              value={highlights.totalTeams}
              sub={`${highlights.totalPlayers} jugadores`}
              onClick={() => goTo('teams')}
            />
          </div>
        )}

        {/* Module grid */}
        <div>
          <h2 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-3">
            Módulos de análisis
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {MODULES.map(({ icon: Icon, label, description, subPath, accent }) => (
              <button
                key={subPath}
                onClick={() => goTo(subPath)}
                className="card p-4 text-left hover:border-surface-hover hover:bg-surface-hover
                           transition-colors group cursor-pointer"
              >
                <Icon className={`w-5 h-5 mb-3 ${accent} group-hover:scale-110 transition-transform`} />
                <p className="text-sm font-medium text-ink-primary mb-1">{label}</p>
                <p className="text-xs text-ink-secondary leading-relaxed">{description}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
