/**
 * Columns of the tables of teams (basic and advanced): ONE definition for the page of team stats and the page of comparisons (issue #607), so a figure is named,
 * rounded and ordered the same everywhere.
 */
import type { TeamStat } from '@/api/client'

export interface ColDef {
  key: keyof TeamStat
  header: string
  decimals?: number
  pct?: boolean
  /** Lower value = better for this stat */
  reverse?: boolean
  /** Count columns: no trend badge, no quartile colouring */
  count?: boolean
  /** Column width in pixels for DataTable */
  size?: number
}

export const BASIC_COL_DEFS: ColDef[] = [
  { key: 'total_games',                  header: 'PJ',     decimals: 0, count: true, size: 44 },
  { key: 'games_home',                   header: 'L',      decimals: 0, count: true, size: 44 },
  { key: 'games_away',                   header: 'V',      decimals: 0, count: true, size: 44 },
  { key: 'points_per_game',              header: 'PPP',    size: 58 },
  { key: 'points_against_per_game',      header: 'PPC',    reverse: true, size: 58 },
  { key: 'fg2_percentage',               header: '%T2',    pct: true, size: 62 },
  { key: 'fg3_percentage',               header: '%T3',    pct: true, size: 62 },
  { key: 'ft_percentage',                header: '%TL',    pct: true, size: 62 },
  { key: 'rebounds_per_game',            header: 'Reb',    size: 56 },
  { key: 'offensive_rebounds_per_game',  header: 'RO',     size: 48 },
  { key: 'defensive_rebounds_per_game',  header: 'RD',     size: 48 },
  { key: 'assists_per_game',             header: 'Ast',    size: 48 },
  { key: 'steals_per_game',              header: 'Rob',    size: 48 },
  { key: 'turnovers_per_game',           header: 'Perd',   reverse: true, size: 52 },
  { key: 'blocks_per_game',              header: 'Tap',    size: 48 },
]

export const ADVANCED_COL_DEFS: ColDef[] = [
  { key: 'total_games',               header: 'PJ',     decimals: 0, count: true, size: 44 },
  { key: 'possessions_per_game',      header: 'Pos',    size: 52 },
  { key: 'offensive_rating',          header: 'OER',    size: 56 },
  { key: 'defensive_rating',          header: 'DER',    reverse: true, size: 56 },
  { key: 'net_rating',                header: 'Net',    size: 56 },
  { key: 'efg_percentage',            header: 'eFG%',   pct: true, size: 62 },
  { key: 'true_shooting',             header: 'TS%',    pct: true, size: 58 },
  { key: 'three_point_rate',          header: '3Pr%',   pct: true, size: 58 },
  { key: 'free_throw_rate',           header: 'FTr%',   pct: true, size: 58 },
  { key: 'assist_fg_rate',            header: 'AST/FG', pct: true, size: 68 },
  { key: 'assist_rate',               header: 'AST%',   pct: true, size: 60 },
  { key: 'turnover_rate',             header: 'TOV%',   pct: true, reverse: true, size: 62 },
  { key: 'steal_rate',                header: 'ROB%',   pct: true, size: 62 },
  { key: 'block_rate',                header: 'TAP%',   pct: true, size: 62 },
  { key: 'offensive_rebound_rate',    header: 'ORB%',   pct: true, size: 62 },
  { key: 'defensive_rebound_rate',    header: 'RD%',    pct: true, size: 60 },
]

/** Columns where lower is better (for DataTable quartile colouring) */
export const REVERSE_BASIC = BASIC_COL_DEFS.filter(d => d.reverse).map(d => d.key as string)
export const REVERSE_ADV   = ADVANCED_COL_DEFS.filter(d => d.reverse).map(d => d.key as string)
