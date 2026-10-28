/**
 * CollectionHub — dashboard overview for a loaded collection.
 *
 * Shows key highlights (top scorer, best OER, best record, pace)
 * and a card for EVERY page of the competition, in the groups of the menu (lib/nav.ts, issue #191).
 */
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useCollection } from '@/context/CollectionContext'
import { getTeamStats, getPlayerStats, type TeamStat, type PlayerStat } from '@/api/client'
import StatCard from '@/components/ui/StatCard'
import Button from '@/components/ui/Button'
import PageHeader from '@/components/ui/PageHeader'
import PageTransition from '@/components/ui/PageTransition'
import { NAV_GROUPS } from '@/lib/nav'
import { fmt } from '@/lib/utils'

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

  const collectionName = collection?.name
  useEffect(() => {
    if (!collectionName) return
    setLoading(true)
    Promise.all([
      getTeamStats(collectionName),
      getPlayerStats(collectionName),
    ])
      .then(([teamData, playerData]) => {
        setHighlights(deriveHighlights(teamData.team_stats, playerData))
      })
      .catch(() => setHighlights(null))
      .finally(() => setLoading(false))
  }, [collectionName])

  const goTo = (subPath: string) => navigateTo(subPath)

  if (!collection) {
    return (
      <div className="flex items-center justify-center h-64">
        <Button onClick={() => navigate('/')}>Seleccionar colección</Button>
      </div>
    )
  }

  return (
    <PageTransition>
      <div className="space-y-8">
        {/* Title */}
        <PageHeader title={collection.label} subtitle={collection.isFbcyl ? 'FBCYL — Castilla y León' : 'FEB — Liga Nacional'} />

        {/* Highlight stats */}
        {loading ? (
          <div className="flex items-center gap-2 text-ink-muted text-sm">
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
                tone="ok"
                onClick={() => goTo('rankings')}
              />
            )}
            {highlights.bestOER && (
              <StatCard
                label="Mejor OER"
                value={fmt(highlights.bestOER.oer)}
                sub={highlights.bestOER.team}
                tone="secondary"
                onClick={() => goTo('teams')}
              />
            )}
            {highlights.avgPace && (
              <StatCard
                label="Ritmo medio"
                value={fmt(highlights.avgPace)}
                sub="posesiones / partido"
                tone="neutral"
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

        {/* A card for every page, in the groups of the menu */}
        {NAV_GROUPS.map(group => (
          <section key={group.label} aria-labelledby={`hub-${group.label}`}>
            <h2 id={`hub-${group.label}`} className="text-xs font-semibold text-ink-faint uppercase tracking-wider mb-3">{group.label}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {group.items.map(({ icon: Icon, label, title, description, subPath }) => (
                <Link
                  key={subPath}
                  to={`/${encodeURIComponent(collection.name)}/${subPath}`}
                  className="card group p-4 transition-colors hover:border-accent/40 hover:bg-surface-raised"
                >
                  <Icon className="mb-3 h-5 w-5 text-accent-text transition-transform group-hover:scale-110" />
                  <p className="mb-1 text-sm font-medium text-ink">{title ?? label}</p>
                  <p className="text-xs leading-relaxed text-ink-muted">{description}</p>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </PageTransition>
  )
}
