/** Collections: the team names of a competition and the list of competitions (issues #201, #761). */
import { fromSource } from '@/datasource/resolve'
import { localCollectionList, localTeamNames } from '@/localdata/source'
import { loadReportTeams } from '@/webdata/client'
import { get } from './http'

// ── Collections ──────────────────────────────────────────────────────────────

/** Stable team entry — ID survives sponsor renames. */
export interface TeamEntry {
  id: string
  name: string
}

export const getTeamsInCollection = (collection: string) =>
  fromSource('team-stats', () => localTeamNames(collection), () => get<string[]>(`/collections/?collection=${encodeURIComponent(collection)}`))

/** The {id, name} of the teams of a competition: from the index of its reports in the publication, or from the API in development (`?data=api`). */
export const getLiveTeamNames = (collection: string) =>
  fromSource('report-teams', () => loadReportTeams(collection), () => get<TeamEntry[]>(`/teams/${encodeURIComponent(collection)}/teams`))

// ── Collections management ────────────────────────────────────────────────────

export interface CollectionInfo {
  name: string
  league: 'FEB' | 'FBCYL' | (string & {})   // the ámbito: new federations arrive as data (#761)
  competition: string
  season: string
  group: string
  game_count: number
  /** From the catalogue through the manifest (#914): `formacion` for the youth championships, absent (older publications, the API) is senior */
  category?: 'senior' | 'formacion'
  age_group?: 'U14' | 'U16' | 'U18' | 'U20'
  /** The name people read, when the catalogue has one (the youth codes of FEB do not: `C ESP CLUBES JR FEM`) */
  competition_label?: string
}

export const getCollectionList = () =>
  fromSource('collections', () => localCollectionList(), () => get<CollectionInfo[]>('/collections/list'))
