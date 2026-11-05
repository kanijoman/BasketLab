/** Multi-phase: the competition phases combined (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localMultiPlayerStats, localMultiTeamStats, localSiblingCollections } from '@/localdata/source'
import { get } from './http'
import type { PlayerStat } from './players'
import type { TeamStat } from './teams'

// ── Multi-phase ───────────────────────────────────────────────────────────────

export const getMultiTeamStats = (collections: string[], is_fbcyl = false) =>
  fromSource(
    'multi-phase',
    () => localMultiTeamStats(collections),
    () => get<TeamStat[]>(`/multi/team-stats?collections=${collections.map(encodeURIComponent).join(',')}&is_fbcyl=${is_fbcyl}`),
  )

export const getMultiPlayerStats = (collections: string[], is_fbcyl = false) =>
  fromSource(
    'multi-phase',
    () => localMultiPlayerStats(collections),
    () => get<PlayerStat[]>(`/multi/player-stats?collections=${collections.map(encodeURIComponent).join(',')}&is_fbcyl=${is_fbcyl}`),
  )

export const getSiblingCollections = (collection: string) =>
  fromSource(
    'multi-phase',
    () => localSiblingCollections(collection),
    () => get<string[]>(`/multi/sibling-collections?collection=${encodeURIComponent(collection)}`),
  )
