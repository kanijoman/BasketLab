/** Possessions: the table and its CSV downloads (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localPossessionCsv, localPossessionStats } from '@/localdata/source'

// ── Possessions ───────────────────────────────────────────────────────────────

export const getPossessionStats = (collection: string) =>
  fromSource(
    'possessions',
    () => localPossessionStats(collection),            // the endpoint takes no filter
  )

/** The BOM Excel needs to read a CSV as UTF-8: once, at the start of the file. */
const BOM = '﻿'

/** A CSV the page offers as a download: made here from the published text, or the API's file. */
async function possessionCsv(collection: string, kind: 'possessions' | 'quality'): Promise<Blob> {
  return fromSource(
    'possessions',
    async () => {
      const text = await localPossessionCsv(collection, kind)
      return text === null ? null : new Blob([BOM, text], { type: 'text/csv;charset=utf-8' })
    },
  )
}

/** One row per possession of every game of the competition (the file of «Exportar CSV»). */
export const fetchPossessionsCsv = (collection: string): Promise<Blob> => possessionCsv(collection, 'possessions')

/** PBP against box score per team and game (the file of «Calidad PBP CSV»). */
export const fetchPossessionQualityCsv = (collection: string): Promise<Blob> => possessionCsv(collection, 'quality')

export interface PossessionStat {
  team_name: string
  team_id?: string
  possessions_per_game: number
  points_per_100: number
  oer: number
  der: number
  pace: number
  net_rating: number
  total_games: number
  avg_duration: number | null
  pct_fast: number | null
  pct_medium: number | null
  pct_slow: number | null
  oer_fast: number | null
  oer_medium: number | null
  oer_slow: number | null
  est_possessions_per_game: number | null
  rival_pct_fast: number | null
  rival_pct_medium: number | null
  rival_pct_slow: number | null
  rival_oer_fast: number | null
  rival_oer_medium: number | null
  rival_oer_slow: number | null
  rival_avg_duration: number | null
  rival_avg_duration_general: number | null
  rival_pace_differential: number | null
  [key: string]: unknown
}
