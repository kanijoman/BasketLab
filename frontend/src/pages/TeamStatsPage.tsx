/**
 * TeamStatsPage — season statistics for all teams in a collection.
 *
 * Tabs: Básico | Avanzado | Rivales
 * Filters: venue (home/away), result (won/lost), date range
 * Quartile colouring via DataTable
 * Trend badges inline in every numeric cell when a date filter is active
 * Export: CSV / PNG / PDF via DataTable > ExportButton
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { BarChart2, Shield, Zap } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getTeamStats, getTeamQuartiles, type TeamStat, type TeamFilters } from '@/api/client'
import { fmt, fmtPct, getTrend } from '@/lib/utils'
import PageTransition from '@/components/ui/PageTransition'
import FilterBar, { useFilters } from '@/components/ui/FilterBar'
import DataTable, { type QuartileMap } from '@/components/ui/DataTable'
import StatCard from '@/components/ui/StatCard'
import TrendBadge from '@/components/ui/TrendBadge'

// -- Column metadata (key, header, display options) ----------------------------

interface ColDef {
  key: keyof TeamStat
  header: string
  decimals?: number
  pct?: boolean
  /** Lower value = better for this stat */
  reverse?: boolean
  /** Count columns: no trend badge, no quartile colouring */
  count?: boolean
}

const BASIC_COL_DEFS: ColDef[] = [
  { key: 'total_games',                  header: 'PJ',     decimals: 0, count: true },
  { key: 'games_home',                   header: 'L',      decimals: 0, count: true },
  { key: 'games_away',                   header: 'V',      decimals: 0, count: true },
  { key: 'points_per_game',              header: 'PPP' },
  { key: 'points_against_per_game',      header: 'PPC',    reverse: true },
  { key: 'fg2_percentage',               header: '%T2',    pct: true },
  { key: 'fg3_percentage',               header: '%T3',    pct: true },
  { key: 'ft_percentage',                header: '%TL',    pct: true },
  { key: 'rebounds_per_game',            header: 'Reb' },
  { key: 'offensive_rebounds_per_game',  header: 'RO' },
  { key: 'defensive_rebounds_per_game',  header: 'RD' },
  { key: 'assists_per_game',             header: 'Ast' },
  { key: 'steals_per_game',              header: 'Rob' },
  { key: 'turnovers_per_game',           header: 'Perd',   reverse: true },
  { key: 'blocks_per_game',              header: 'Tap' },
]

const ADVANCED_COL_DEFS: ColDef[] = [
  { key: 'total_games',               header: 'PJ',     decimals: 0, count: true },
  { key: 'possessions_per_game',      header: 'Pos' },
  { key: 'offensive_rating',          header: 'OER' },
  { key: 'defensive_rating',          header: 'DER',    reverse: true },
  { key: 'net_rating',                header: 'Net' },
  { key: 'efg_percentage',            header: 'eFG%',   pct: true },
  { key: 'true_shooting',             header: 'TS%',    pct: true },
  { key: 'three_point_rate',          header: '3Pr%',   pct: true },
  { key: 'free_throw_rate',           header: 'FTr%',   pct: true },
  { key: 'assist_fg_rate',            header: 'AST/FG', pct: true },
  { key: 'assist_rate',               header: 'AST%',   pct: true },
  { key: 'turnover_rate',             header: 'TOV%',   pct: true, reverse: true },
  { key: 'steal_rate',                header: 'ROB%',   pct: true },
  { key: 'block_rate',                header: 'TAP%',   pct: true },
  { key: 'offensive_rebound_rate',    header: 'ORB%',   pct: true },
  { key: 'defensive_rebound_rate',    header: 'RD%',    pct: true },
]

/** Columns where lower is better (for DataTable quartile colouring) */
const REVERSE_BASIC = BASIC_COL_DEFS.filter(d => d.reverse).map(d => d.key as string)
const REVERSE_ADV   = ADVANCED_COL_DEFS.filter(d => d.reverse).map(d => d.key as string)

// -- Column factory ------------------------------------------------------------

function nameCol(): ColumnDef<TeamStat, unknown> {
  return {
    id: 'team_name',
    accessorKey: 'team_name',
    header: 'Equipo',
    cell: ({ getValue }) => (
      <span className="font-medium text-ink-primary whitespace-nowrap">
        {getValue() as string}
      </span>
    ),
    enableSorting: true,
  }
}

/**
 * Build a ColumnDef from a ColDef descriptor.
 * When seasonByName is provided (date filter active) and the column is not a
 * count, the cell also shows an inline TrendBadge.
 */
function buildCol(
  def: ColDef,
  seasonByName: Record<string, TeamStat> | null,
): ColumnDef<TeamStat, unknown> {
  const { key, header, decimals = 1, pct = false, reverse = false, count = false } = def
  const showTrend = !count && seasonByName !== null

  return {
    id: key as string,
    accessorKey: key as string,
    header,
    cell: ({ getValue, row }) => {
      const v = getValue() as number | null | undefined
      const formatted = pct ? fmtPct(v) : fmt(v, decimals)

      if (!showTrend) return formatted

      const teamName = (row.original as TeamStat).team_name
      const seasonRow = seasonByName![teamName]
      const seasonVal = seasonRow ? (seasonRow[key] as number | null | undefined) : null

      return (
        <span className="inline-flex items-center gap-1.5">
          <span>{formatted}</span>
          <TrendBadge recent={v} season={seasonVal} reverse={reverse} className="text-[10px]" />
        </span>
      )
    },
  }
}

function buildCols(
  defs: ColDef[],
  seasonByName: Record<string, TeamStat> | null,
): ColumnDef<TeamStat, unknown>[] {
  return [nameCol(), ...defs.map(d => buildCol(d, seasonByName))]
}

// -- Helpers -------------------------------------------------------------------

function buildQuartileMap(raw: Record<string, Record<string, number>>): QuartileMap {
  const map: QuartileMap = {}
  for (const [key, vals] of Object.entries(raw)) {
    if (vals?.q1 != null && vals?.q2 != null && vals?.q3 != null) {
      map[key] = [vals.q1, vals.q2, vals.q3]
    }
  }
  return map
}

function mean(rows: TeamStat[], key: keyof TeamStat): number {
  if (!rows.length) return 0
  const sum = rows.reduce((s, r) => s + ((r[key] as number) ?? 0), 0)
  return sum / rows.length
}

// -- Tabs config ---------------------------------------------------------------

const TABS = [
  { id: 'basic',    label: 'Básico',   Icon: BarChart2 },
  { id: 'advanced', label: 'Avanzado', Icon: Zap       },
  { id: 'rivals',   label: 'Rivales',  Icon: Shield    },
] as const
type TabId = (typeof TABS)[number]['id']

// -- Component -----------------------------------------------------------------

export default function TeamStatsPage() {
  const { collection } = useCollection()
  const filters = useFilters()
  const [tab, setTab] = useState<TabId>('basic')

  const apiFilters: TeamFilters = useMemo(() => ({
    venue:  filters.venue  || undefined,
    result: filters.result || undefined,
    from:   filters.dateFrom || undefined,
    to:     filters.dateTo   || undefined,
  }), [filters])

  // Season-baseline query (no date filter) — used for trend comparison
  const hasDateFilter = Boolean(filters.dateFrom)
  const baselineFilters: TeamFilters = useMemo(() => ({
    venue:  filters.venue  || undefined,
    result: filters.result || undefined,
  }), [filters.venue, filters.result])

  const { data: seasonData } = useQuery({
    queryKey:  ['team-stats-season', collection?.name, baselineFilters],
    queryFn:   () => getTeamStats(collection!.name, baselineFilters),
    enabled:   Boolean(collection) && hasDateFilter,
    staleTime: 10 * 60_000,
  })

  const { data: statsData, isLoading: loadingStats } = useQuery({
    queryKey: ['team-stats', collection?.name, apiFilters],
    queryFn:  () => getTeamStats(collection!.name, apiFilters),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
  })

  const { data: quartilesRaw } = useQuery({
    queryKey: ['team-quartiles', collection?.name],
    queryFn:  () => getTeamQuartiles(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 10 * 60_000,
  })

  const teamRows    = statsData?.team_stats ?? []
  const rivalRows   = statsData?.opponent_stats ?? []

  // Map team name → full-season row for comparison
  const seasonByName = useMemo(() => {
    const m: Record<string, TeamStat> = {}
    for (const r of (seasonData?.team_stats ?? [])) m[r.team_name] = r
    return m
  }, [seasonData])
  const quartileMap = useMemo(
    () => (quartilesRaw ? buildQuartileMap(quartilesRaw) : {}),
    [quartilesRaw],
  )

  // Trend source: season baseline for team rows; no trend for rivals
  const trendSource = useMemo(
    () => (hasDateFilter && tab !== 'rivals' ? seasonByName : null),
    [hasDateFilter, tab, seasonByName],
  )

  const basicCols    = useMemo(() => buildCols(BASIC_COL_DEFS,    trendSource), [trendSource])
  const advancedCols = useMemo(() => buildCols(ADVANCED_COL_DEFS, trendSource), [trendSource])

  // Highlights: show per-stat trend on chips when date filter active
  const seasonHighlights = useMemo(() => {
    if (!hasDateFilter || !seasonData?.team_stats?.length) return null
    const rows = seasonData.team_stats
    return {
      pos: mean(rows as TeamStat[], 'possessions_per_game'),
      oer: mean(rows as TeamStat[], 'offensive_rating'),
      ppg: mean(rows as TeamStat[], 'points_per_game'),
    }
  }, [hasDateFilter, seasonData])

  const highlights = useMemo(() => ({
    pos: mean(teamRows, 'possessions_per_game'),
    oer: mean(teamRows, 'offensive_rating'),
    ppg: mean(teamRows, 'points_per_game'),
  }), [teamRows])

  const [rivalsView, setRivalsView] = useState<'basic' | 'advanced'>('basic')

  const activeData = tab === 'rivals' ? rivalRows : teamRows
  const activeCols =
    tab === 'advanced' || (tab === 'rivals' && rivalsView === 'advanced')
      ? advancedCols
      : basicCols
  const activeRev =
    tab === 'advanced' || (tab === 'rivals' && rivalsView === 'advanced')
      ? REVERSE_ADV
      : REVERSE_BASIC

  if (!collection) {
    return (
      <PageTransition>
        <p className="text-center text-ink-muted mt-16">
          Selecciona una colección para continuar.
        </p>
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <div className="space-y-4">

        {/* Page header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-ink-primary">Estadísticas de Equipo</h1>
            <p className="text-sm text-ink-muted mt-0.5">{collection.label}</p>
          </div>
          <FilterBar showDate />
        </div>

        {/* Highlight stat cards — show trend vs full season when date filter active */}
        <div className="grid grid-cols-3 gap-3">
          {(() => {
            const posTrend  = seasonHighlights ? getTrend(highlights.pos, seasonHighlights.pos)  : null
            const oerTrend  = seasonHighlights ? getTrend(highlights.oer, seasonHighlights.oer)  : null
            const ppgTrend  = seasonHighlights ? getTrend(highlights.ppg, seasonHighlights.ppg)  : null
            return (
              <>
                <StatCard
                  label="Pos/Partido"
                  value={fmt(highlights.pos)}
                  trend={posTrend?.symbol}
                  trendClass={posTrend?.className}
                />
                <StatCard
                  label="OER Medio"
                  value={fmt(highlights.oer)}
                  accent="green"
                  trend={oerTrend?.symbol}
                  trendClass={oerTrend?.className}
                />
                <StatCard
                  label="PPP Medio"
                  value={fmt(highlights.ppg)}
                  trend={ppgTrend?.symbol}
                  trendClass={ppgTrend?.className}
                />
              </>
            )
          })()}
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-surface-border">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={[
                'flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px',
                tab === id
                  ? 'border-brand-500 text-brand-400'
                  : 'border-transparent text-ink-muted hover:text-ink-primary',
              ].join(' ')}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
          {tab === 'rivals' && (
            <div className="ml-auto mb-1 flex rounded-lg overflow-hidden border border-surface-border">
              {(['basic', 'advanced'] as const).map(v => (
                <button
                  key={v}
                  onClick={() => setRivalsView(v)}
                  className={[
                    'px-3 py-1 text-xs font-medium transition-colors',
                    rivalsView === v
                      ? 'bg-brand-600/30 text-brand-400'
                      : 'text-ink-secondary hover:bg-surface-hover hover:text-ink-primary',
                  ].join(' ')}
                >
                  {v === 'basic' ? 'Básico' : 'Avanzado'}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Data table */}
        <DataTable
          columns={activeCols}
          data={activeData}
          quartiles={quartileMap}
          reverseColumns={activeRev}
          loading={loadingStats}
          searchable
          searchPlaceholder="Buscar equipo…"
          exportOptions={{
            filename:   `equipos_${tab}_${collection.name}`,
            pdfTitle:   `Estadísticas de Equipo — ${tab}`,
            csvHeaders: activeCols.map(c => ({
              key:   String((c as { accessorKey?: string }).accessorKey ?? c.id ?? ''),
              label: String(c.header ?? ''),
            })),
            csvData: activeData,
          }}
        />

      </div>
    </PageTransition>
  )
}
