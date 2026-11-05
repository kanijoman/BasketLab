/** Collections: the team names of a competition and the list of competitions (issues #201, #761). */
import { fromSource } from '@/datasource/resolve'
import { localCollectionList, localTeamNames } from '@/localdata/source'
import { get } from './http'

// ── Collections ──────────────────────────────────────────────────────────────

/** Stable team entry — ID survives sponsor renames. */
export interface TeamEntry {
  id: string
  name: string
}

export const getTeamsInCollection = (collection: string) =>
  fromSource('team-stats', () => localTeamNames(collection), () => get<string[]>(`/collections/?collection=${encodeURIComponent(collection)}`))

// ── Collections management ────────────────────────────────────────────────────

export interface CollectionInfo {
  name: string
  league: 'FEB' | 'FBCYL' | (string & {})   // the ámbito: new federations arrive as data (#761)
  competition: string
  season: string
  group: string
  game_count: number
}

export const getCollectionList = () =>
  fromSource('collections', () => localCollectionList(), () => get<CollectionInfo[]>('/collections/list'))
