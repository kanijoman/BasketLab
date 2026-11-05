/** Reports and match analysis (issue #201). */
import { fromSource } from '@/datasource/resolve'
import { localMatchAnalysis, localMatchList } from '@/localdata/source'
import { get } from './http'

// ── Match Analysis ────────────────────────────────────────────────────────────

export interface MatchSummary {
  match_id: number | string
  date: string
  round: string
  venue: string
  home_team: string
  away_team: string
  home_score: number
  away_score: number
}

/** One statistic of the comparison of a game: its value for each team and who is better (Análisis de partido). */
export interface MatchComparisonRow {
  stat_key: string
  label: string
  section: string
  home_value: number
  away_value: number
  delta: number
  winner: 'home' | 'away' | 'tie'
  lower_is_better: boolean
}

export interface MatchAnalysis {
  home: { team_name: string; [key: string]: unknown }
  away: { team_name: string; [key: string]: unknown }
  comparison: MatchComparisonRow[]
}

// With the dataset `matches` on (`?data=local`, issue #677) the list and the analysis of a match are the ones computed when the competition was published.
export const getMatchList = (collection: string, is_fbcyl = false) =>
  fromSource(
    'matches',
    () => localMatchList(collection),
    () => get<MatchSummary[]>(`/matches/${encodeURIComponent(collection)}?is_fbcyl=${is_fbcyl}`),
  )

export const getMatchAnalysis = (
  collection: string,
  matchId: string | number,
  is_fbcyl = false,
) =>
  fromSource(
    'matches',
    () => localMatchAnalysis(collection, matchId),
    () => get<MatchAnalysis>(`/matches/${encodeURIComponent(collection)}/${matchId}?is_fbcyl=${is_fbcyl}`),
  )
