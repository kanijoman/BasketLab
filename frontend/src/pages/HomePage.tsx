/**
 * HomePage — landing page: the competition is chosen by ámbito → temporada → competición → grupo (issue #761, `lib/collectionPicker`),
 * with the latest season preselected, and the page links to the one chosen.
 * Recent collections are stored in localStorage for quick access at the top.
 * If the database is empty, directs the user to the Admin panel.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Clock, ChevronRight, Database, RefreshCw } from 'lucide-react'
import { getCollectionList, type CollectionInfo } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Button, { IconButton } from '@/components/ui/Button'
import BrandLogo from '@/components/BrandLogo'
import CollectionPicker from '@/components/CollectionPicker'
import { pickCollection, type Selection } from '@/lib/collectionPicker'
import { loadRecents, pruneRecents, saveRecent, saveRecents, type RecentCollection } from '@/lib/recents'
import { DataUnavailable } from '@/datasource/resolve'

// ── Sub-components ────────────────────────────────────────────────────────────

/** The competition the selectors resolve to: a link to it. */
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

// ── Page ──────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const [recents, setRecents] = useState<RecentCollection[]>([])
  const [selection, setSelection] = useState<Selection>({})

  useEffect(() => {
    setRecents(loadRecents())
  }, [])

  const { data: collections, isLoading, isError, error, refetch } = useQuery({
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

  const picked = useMemo(() => pickCollection(collections ?? [], selection).collection, [collections, selection])

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
                <p className="text-sm text-bad">{error instanceof DataUnavailable ? error.message : 'No se pudieron cargar los datos.'}</p>
                <Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button>
              </div>
            )}

            {!isLoading && !isError && collections?.length === 0 && (
              <div className="card p-8 flex flex-col items-center gap-3 text-center">
                <Database className="w-8 h-8 text-ink-faint opacity-50" />
                <div>
                  <p className="text-sm font-medium text-ink">Base de datos vacía</p>
                  <p className="text-xs text-ink-muted mt-1">
                    Los datos los carga el refresco programado del archivo; aún no ha publicado ninguna competición.
                  </p>
                </div>
              </div>
            )}

            {!isLoading && !isError && collections && collections.length > 0 && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <CollectionPicker list={collections} value={selection} onChange={next => setSelection(next)} />
                </div>
                {picked && <CollectionCard col={picked} onClick={() => handleNavigate(picked)} />}
              </div>
            )}
          </div>

        </div>
      </div>
    </PageTransition>
  )
}

