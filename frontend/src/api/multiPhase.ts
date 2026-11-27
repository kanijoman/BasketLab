/** Multi-phase: the competition phases combined (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localMultiPlayerStats, localMultiTeamStats, localSiblingCollections } from '@/localdata/source'

// ── Multi-phase ───────────────────────────────────────────────────────────────

export const getMultiTeamStats = (collections: string[]) =>
  fromSource(
    'multi-phase',
    () => localMultiTeamStats(collections),
  )

export const getMultiPlayerStats = (collections: string[]) =>
  fromSource(
    'multi-phase',
    () => localMultiPlayerStats(collections),
  )

export const getSiblingCollections = (collection: string) =>
  fromSource(
    'multi-phase',
    () => localSiblingCollections(collection),
  )
