/**
 * HomePage â€” landing page showing available collections from MongoDB.
 *
 * Groups collections by league â†’ competition â†’ season desc â†’ group.
 * Recent collections are stored in localStorage for quick access at the top.
 * If the database is empty, directs the user to the Admin panel.
 */
import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Clock, ChevronRight, Database, Settings, RefreshCw } from 'lucide-react'
import { getCollectionList, type CollectionInfo } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

// â”€â”€ Recent collections (localStorage) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const RECENTS_KEY = 'basketlab-recent-collections'
const MAX_RECENTS = 5

interface RecentCollection {
  name: string
  label: string
  isFbcyl: boolean
  accessedAt: string
}

function loadRecents(): RecentCollection[] {
  try {
    return JSON.parse(localStorage.getItem(RECENTS_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function saveRecent(name: string, isFbcyl: boolean) {
  const recents = loadRecents().filter(r => r.name !== name)
  const parts = name.split('_')
  const label = parts.length > 1 ? `${parts[0]} · ${parts.slice(1).join(' · ')}` : name
  recents.unshift({ name, label, isFbcyl, accessedAt: new Date().toISOString() })
  try {
    localStorage.setItem(RECENTS_KEY, JSON.stringify(recents.slice(0, MAX_RECENTS)))
  } catch { /* ignore */ }
}

// â”€â”€ Grouping helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface GroupedCompetition {
  competition: string
  seasons: { season: string; collections: CollectionInfo[] }[]
}

interface GroupedLeague {
  league: string
  competitions: GroupedCompetition[]
}

function groupCollections(list: CollectionInfo[]): GroupedLeague[] {
  const byLeague = new Map<string, Map<string, Map<string, CollectionInfo[]>>>()

  for (const col of list) {
    if (!byLeague.has(col.league)) byLeague.set(col.league, new Map())
    const byComp = byLeague.get(col.league)!
    if (!byComp.has(col.competition)) byComp.set(col.competition, new Map())
    const bySeason = byComp.get(col.competition)!
    if (!bySeason.has(col.season)) bySeason.set(col.season, [])
    bySeason.get(col.season)!.push(col)
  }

  const leagues: GroupedLeague[] = []
  for (const [league, comps] of [...byLeague.entries()].sort()) {
    const competitions: GroupedCompetition[] = []
    for (const [competition, seasons] of [...comps.entries()].sort()) {
      const seasonList = [...seasons.entries()]
        .sort((a, b) => b[0].localeCompare(a[0])) // season desc
        .map(([season, cols]) => ({
          season,
          collections: cols.sort((a, b) => (a.group ?? '').localeCompare(b.group ?? '')),
        }))
      competitions.push({ competition, seasons: seasonList })
    }
    leagues.push({ league, competitions })
  }
  return leagues
}

// â”€â”€ Sub-components â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function CollectionCard({ col, onClick }: { col: CollectionInfo; onClick: () => void }) {
  const isFbcyl = col.league === 'FBCYL'
  return (
    <button
      onClick={onClick}
      className="w-full text-left p-3.5 rounded-card border border-surface-border
                 bg-surface-raised hover:border-brand-600/40 hover:bg-surface-hover
                 transition-all group flex items-center justify-between gap-2"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={`text-xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${
          isFbcyl
            ? 'bg-accent-600/20 text-accent-400'
            : 'bg-brand-600/20 text-brand-400'
        }`}>
          {col.group ? `Grupo ${col.group}` : col.season}
        </span>
        <span className="text-sm text-ink-primary font-medium truncate">
          {col.competition} {col.season}{col.group ? ` â€“ ${col.group}` : ''}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-xs text-ink-muted">{col.game_count} partidos</span>
        <ChevronRight className="w-3.5 h-3.5 text-ink-muted group-hover:text-ink-primary transition-colors" />
      </div>
    </button>
  )
}

function LeagueSection({
  group,
  onNavigate,
}: {
  group: GroupedLeague
  onNavigate: (col: CollectionInfo) => void
}) {
  const isFbcyl = group.league === 'FBCYL'
  const total = group.competitions.reduce(
    (n, c) => n + c.seasons.reduce((s, ss) => s + ss.collections.length, 0),
    0,
  )
  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <span className={`text-xs px-2.5 py-1 rounded-pill font-semibold ${
          isFbcyl ? 'bg-accent-600/20 text-accent-400' : 'bg-brand-600/20 text-brand-400'
        }`}>
          {group.league}
        </span>
        <span className="text-xs text-ink-muted">{total} colecciones</span>
      </div>

      <div className="space-y-5">
        {group.competitions.map(comp => (
          <div key={comp.competition} className="space-y-2">
            <p className="text-xs font-semibold text-ink-secondary uppercase tracking-wider">
              {comp.competition}
            </p>
            {comp.seasons.map(s => (
              <div key={s.season} className="space-y-1.5">
                {s.collections.length > 1 && (
                  <p className="text-xs text-ink-muted ml-1">Temporada {s.season}</p>
                )}
                {s.collections.map(col => (
                  <CollectionCard key={col.name} col={col} onClick={() => onNavigate(col)} />
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}

// â”€â”€ Page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export default function HomePage() {
  const navigate = useNavigate()
  const [recents, setRecents] = useState<RecentCollection[]>([])

  useEffect(() => {
    setRecents(loadRecents())
  }, [])

  const { data: collections, isLoading, isError, refetch } = useQuery({
    queryKey: ['collections-list'],
    queryFn: getCollectionList,
    staleTime: 30_000,
  })

  function handleNavigate(col: CollectionInfo) {
    saveRecent(col.name, col.league === 'FBCYL')
    navigate(`/${encodeURIComponent(col.name)}`)
  }

  const grouped = collections ? groupCollections(collections) : []

  return (
    <PageTransition>
      <div className="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-start px-4 py-10">
        <div className="w-full max-w-2xl space-y-8">

          {/* Header */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center gap-3 mb-4">
              <img
                src="/logo.png"
                alt="BasketLab"
                className="h-12 w-12 rounded-xl shadow-card"
                onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
              <h1 className="text-3xl font-bold text-ink-primary tracking-tight">BasketLab</h1>
            </div>
            <p className="text-ink-secondary text-sm">
              Análisis estadístico de baloncesto · Ligas españolas FEB / FBCYL
            </p>
          </div>

          {/* Recent collections */}
          {recents.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Clock className="w-3.5 h-3.5" />
                Accesos recientes
              </div>
              <div className="space-y-1">
                {recents.map(r => (
                  <button
                    key={r.name}
                    onClick={() => navigate(`/${encodeURIComponent(r.name)}`)}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg
                               bg-surface-raised border border-surface-border
                               hover:border-brand-600/40 hover:bg-surface-hover
                               transition-colors text-left group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${
                        r.isFbcyl
                          ? 'bg-accent-600/20 text-accent-400'
                          : 'bg-brand-600/20 text-brand-400'
                      }`}>
                        {r.isFbcyl ? 'FBCYL' : 'FEB'}
                      </span>
                      <span className="text-sm text-ink-primary truncate">{r.label}</span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-ink-muted group-hover:text-ink-primary transition-colors shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Collections list */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Database className="w-3.5 h-3.5" />
                Competiciones disponibles
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => refetch()}
                  className="p-1.5 rounded-lg hover:bg-surface-hover text-ink-muted
                             hover:text-ink-primary transition-colors"
                  title="Actualizar lista"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
                <Link
                  to="/admin"
                  className="flex items-center gap-1 text-xs text-ink-muted
                             hover:text-ink-primary transition-colors"
                >
                  <Settings className="w-3.5 h-3.5" />
                  Administrar
                </Link>
              </div>
            </div>

            {isLoading && (
              <div className="space-y-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-12 rounded-card bg-surface-border/40 animate-pulse" />
                ))}
              </div>
            )}

            {isError && (
              <div className="card p-6 text-center space-y-3">
                <p className="text-sm text-down">No se pudo conectar con el servidor.</p>
                <button onClick={() => refetch()} className="btn-secondary text-xs">
                  Reintentar
                </button>
              </div>
            )}

            {!isLoading && !isError && collections?.length === 0 && (
              <div className="card p-8 flex flex-col items-center gap-3 text-center">
                <Database className="w-8 h-8 text-ink-muted opacity-50" />
                <div>
                  <p className="text-sm font-medium text-ink-primary">Base de datos vacía</p>
                  <p className="text-xs text-ink-secondary mt-1">
                    Descarga una competición desde el panel de administración.
                  </p>
                </div>
                <Link to="/admin" className="btn-primary text-sm px-4 py-2">
                  Ir a Administración
                </Link>
              </div>
            )}

            {!isLoading && !isError && grouped.length > 0 && (
              <div className="space-y-8">
                {grouped.map(g => (
                  <LeagueSection key={g.league} group={g} onNavigate={handleNavigate} />
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </PageTransition>
  )
}

