/** Tab "Colecciones": the collections in MongoDB, to open or to delete (issue #195: on the base components). */
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, ExternalLink, RefreshCw, Trash2 } from 'lucide-react'
import { deleteCollection, getCollectionList, type CollectionInfo } from '@/api/client'
import Button, { IconButton } from '@/components/ui/Button'
import EmptyState from '@/components/ui/EmptyState'

export function CollectionsTab({ onOpen }: { onOpen: (name: string) => void }) {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['collections-list'],
    queryFn:  getCollectionList,
    staleTime: 30_000,
  })
  const [deleting, setDeleting] = useState<string | null>(null)

  async function handleDelete(name: string) {
    if (!window.confirm(`¿Eliminar permanentemente la colección "${name}"?\n\nEsta acción no se puede deshacer.`)) return
    setDeleting(name)
    try {
      await deleteCollection(name)
      queryClient.invalidateQueries({ queryKey: ['collections-list'] })
    } catch (err) {
      alert(`Error al eliminar: ${err instanceof Error ? err.message : err}`)
    } finally {
      setDeleting(null)
    }
  }

  if (isLoading) return (
    <div className="space-y-2 mt-4" aria-hidden="true">
      {[1, 2, 3].map(i => <div key={i} className="h-12 rounded-card bg-line/40 animate-pulse" />)}
    </div>
  )

  if (isError) return (
    <div className="mt-4 card p-6 text-center space-y-3">
      <p className="text-sm text-bad">Error al cargar colecciones.</p>
      <Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button>
    </div>
  )

  if (!data?.length) return (
    <div className="mt-4"><EmptyState icon={Database} title="No hay colecciones en la base de datos." /></div>
  )

  return (
    <div className="mt-4 space-y-2">
      <div className="flex justify-end">
        <Button variant="ghost" size="sm" icon={RefreshCw} onClick={() => refetch()}>Actualizar</Button>
      </div>
      {data.map((col: CollectionInfo) => (
        <div key={col.name} className="flex items-center justify-between px-3.5 py-3 rounded-card border border-line bg-surface gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className={`text-xs px-2 py-0.5 rounded-pill font-medium shrink-0 ${col.league === 'FBCYL' ? 'bg-secondary/20 text-secondary-text' : 'bg-accent/20 text-accent-text'}`}>
              {col.league}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink truncate">{col.name}</p>
              <p className="text-xs text-ink-faint">
                {col.competition} · {col.season}{col.group ? ` · Grupo ${col.group}` : ''} · {col.game_count} partidos
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <IconButton icon={ExternalLink} size="sm" label={`Abrir ${col.name}`} onClick={() => onOpen(col.name)} />
            <IconButton icon={Trash2} size="sm" variant="danger" label={`Eliminar ${col.name}`} loading={deleting === col.name} onClick={() => handleDelete(col.name)} />
          </div>
        </div>
      ))}
    </div>
  )
}
