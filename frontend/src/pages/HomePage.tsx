/**
 * HomePage — landing page showing available collections from MongoDB.
 *
 * Groups collections by league → competition → season desc → group.
 * Recent collections are stored in localStorage for quick access at the top.
 * If the database is empty, directs the user to the Admin panel.
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Clock, ChevronRight, Database, Settings, RefreshCw } from 'lucide-react'
import { getCollectionList, type CollectionInfo } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Button, { IconButton } from '@/components/ui/Button'
import BrandLogo from '@/components/BrandLogo'
import { loadRecents, pruneRecents, saveRecent, saveRecents, type RecentCollection } from '@/lib/recents'

// ── Grouping helpers ──────────────────────────────────────────────────────────

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

// ── Sub-components ────────────────────────────────────────────────────────────

function CollectionCard({ col, onClick }: { col: CollectionInfo; onClick: () => void }) {
  const isFbcyl = col.league === 'FBCYL'
  return (
    <Link
      to={`/${encodeURIComponent(col.name)}`}
      onClick={onClick}
      className="w-full text-left p-3.5 rounded-card border border-line
                 bg-surface hover:border-accent/40 hover:bg-surface-raised
                 transition-all group flex items-center justify-between gap-2"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <span className={`text-xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${
          isFbcyl
            ? 'bg-secondary/20 text-secondary-text'
            : 'bg-accent/20 text-accent-text'
        }`}>
          {col.group ? `Grupo ${col.group}` : col.season}
        </span>
        <span className="text-sm text-ink font-medium truncate">
          {col.competition} {col.season}{col.group ? ` – ${col.group}` : ''}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-xs text-ink-faint">{col.game_count} partidos</span>
        <ChevronRight className="w-3.5 h-3.5 text-ink-faint group-hover:text-ink transition-colors" />
      </div>
    </Link>
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
          isFbcyl ? 'bg-secondary/20 text-secondary-text' : 'bg-accent/20 text-accent-text'
        }`}>
          {group.league}
        </span>
        <span className="text-xs text-ink-faint">{total} colecciones</span>
      </div>

      <div className="space-y-5">
        {group.competitions.map(comp => (
          <div key={comp.competition} className="space-y-2">
            <p className="text-xs font-semibold text-ink-muted uppercase tracking-wider">
              {comp.competition}
            </p>
            {comp.seasons.map(s => (
              <div key={s.season} className="space-y-1.5">
                {s.collections.length > 1 && (
                  <p className="text-xs text-ink-faint ml-1">Temporada {s.season}</p>
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [recents, setRecents] = useState<RecentCollection[]>([])

  useEffect(() => {
    setRecents(loadRecents())
  }, [])

  const { data: collections, isLoading, isError, refetch } = useQuery({
    queryKey: ['collections-list'],
    queryFn: getCollectionList,
    staleTime: 30_000,
  })

  // Forget recents whose collection was dropped. An empty answer is ignored: it also happens when the
  // database is unreachable, and that must not wipe the user's list.
  useEffect(() => {
    if (!collections || collections.length === 0) return
    const kept = pruneRecents(loadRecents(), collections)
    saveRecents(kept)
    setRecents(kept)
  }, [collections])

  /** The link takes you to the competition; this remembers it for the recents. */
  function handleNavigate(col: CollectionInfo) {
    saveRecent(col.name, col.league === 'FBCYL')
  }

  const grouped = collections ? groupCollections(collections) : []

  return (
    <PageTransition>
      <div className="min-h-[calc(100vh-3.5rem)] flex flex-col items-center justify-start px-4 py-10">
        <div className="w-full max-w-2xl space-y-8">

          {/* Header */}
          <PageHeader align="center" title={<BrandLogo size="lg" />} subtitle="Análisis estadístico de baloncesto · Ligas españolas FEB / FBCYL"
            className="rounded-lg bg-gradient-to-b from-accent/10 via-accent/5 to-transparent px-4 pb-6 pt-8 [&_h1]:mb-4" />

          {/* Recent collections */}
          {recents.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-ink-faint">
                <Clock className="w-3.5 h-3.5" />
                Accesos recientes
              </div>
              <div className="space-y-1">
                {recents.map(r => (
                  <Link
                    key={r.name}
                    to={`/${encodeURIComponent(r.name)}`}
                    className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg
                               bg-surface border border-line
                               hover:border-accent/40 hover:bg-surface-raised
                               transition-colors text-left group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${
                        r.isFbcyl
                          ? 'bg-secondary/20 text-secondary-text'
                          : 'bg-accent/20 text-accent-text'
                      }`}>
                        {r.isFbcyl ? 'FBCYL' : 'FEB'}
                      </span>
                      <span className="text-sm text-ink truncate">{r.label}</span>
                    </div>
                    <ChevronRight className="w-3.5 h-3.5 text-ink-faint group-hover:text-ink transition-colors shrink-0" />
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Collections list */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-ink-faint">
                <Database className="w-3.5 h-3.5" />
                Competiciones disponibles
              </div>
              <div className="flex items-center gap-3">
                <IconButton icon={RefreshCw} size="sm" label="Actualizar lista" onClick={() => refetch()} />
                <Link
                  to="/admin"
                  className="flex items-center gap-1 text-xs text-ink-faint
                             hover:text-ink transition-colors"
                >
                  <Settings className="w-3.5 h-3.5" />
                  Administrar
                </Link>
              </div>
            </div>

            {isLoading && (
              <div className="space-y-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-12 rounded-card bg-line/40 animate-pulse" />
                ))}
              </div>
            )}

            {isError && (
              <div className="card p-6 text-center space-y-3">
                <p className="text-sm text-bad">No se pudo conectar con el servidor.</p>
                <Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button>
              </div>
            )}

            {!isLoading && !isError && collections?.length === 0 && (
              <div className="card p-8 flex flex-col items-center gap-3 text-center">
                <Database className="w-8 h-8 text-ink-faint opacity-50" />
                <div>
                  <p className="text-sm font-medium text-ink">Base de datos vacía</p>
                  <p className="text-xs text-ink-muted mt-1">
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

