/**
 * CollectionContext — tracks the active competition collection.
 *
 * The collection name (e.g. "FEB_LF2_2025_A") lives in the URL as the first
 * path segment. This context reads it from there and exposes it to all
 * child components so they don't each need `useParams()`.
 */
import {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
} from 'react'
import { useParams, useNavigate } from 'react-router-dom'

export interface CollectionMeta {
  name: string
  isFbcyl: boolean
  /** Display-friendly label derived from the collection name */
  label: string
}

interface CollectionContextValue {
  collection: CollectionMeta | null
  setCollection: (meta: CollectionMeta) => void
  /** Navigate to a sub-route within the current collection */
  navigateTo: (subPath: string) => void
}

const CollectionContext = createContext<CollectionContextValue | null>(null)

/** Parse a collection name into a human-readable label. */
function parseLabel(name: string): string {
  // e.g. "FEB_LF2_2025_A" → "FEB · LF2 2025 · A"
  const parts = name.split('_')
  if (parts.length < 2) return name
  const [league, ...rest] = parts
  return `${league} · ${rest.join(' ')}`
}

export function CollectionProvider({ children }: { children: ReactNode }) {
  const { collection: collectionParam } = useParams<{ collection?: string }>()
  const navigate = useNavigate()
  const [collection, setCollectionState] = useState<CollectionMeta | null>(null)

  // Sync context whenever the URL param changes
  useEffect(() => {
    if (!collectionParam) {
      setCollectionState(null)
      return
    }
    const name = decodeURIComponent(collectionParam)
    setCollectionState(prev =>
      prev?.name === name
        ? prev
        : {
            name,
            isFbcyl: name.toUpperCase().startsWith('FBCYL'),
            label: parseLabel(name),
          },
    )
  }, [collectionParam])

  const setCollection = (meta: CollectionMeta) => setCollectionState(meta)

  const navigateTo = (subPath: string) => {
    if (!collection) return
    navigate(`/${encodeURIComponent(collection.name)}/${subPath}`)
  }

  return (
    <CollectionContext.Provider value={{ collection, setCollection, navigateTo }}>
      {children}
    </CollectionContext.Provider>
  )
}

export function useCollection(): CollectionContextValue {
  const ctx = useContext(CollectionContext)
  if (!ctx) throw new Error('useCollection must be used inside <CollectionProvider>')
  return ctx
}
