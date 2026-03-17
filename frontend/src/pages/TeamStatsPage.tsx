/**
 * TeamStatsPage — season statistics for all teams in a collection.
 *
 * Tabs: Básico | Avanzado | Rivales
 * Filters: venue (home/away), result (won/lost)
 * Quartile colouring via DataTable
 * Export: CSV / PNG / PDF via DataTable > ExportButton
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { BarChart2, Shield, Zap } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getTeamStats, getTeamQuartiles, type TeamStat, type TeamFilters } from '@/api/client'
import { fmt, fmtPct } from '@/lib/utils'
import PageTransition from '@/components/ui/PageTransition'
import FilterBar, { useFilters } from '@/components/ui/FilterBar'
import DataTable, { type QuartileMap } from '@/components/ui/DataTable'
import StatCard from '@/components/ui/StatCard'
import TrendBadge from '@/components/ui/TrendBadge'

// -- Column factory helpers ----------------------------------------------------

function numCol(
  key: string,
  header: string,
  opts: { decimals?: number; pct?: boolean } = {},
): ColumnDef<TeamStat, unknown> {
  const { decimals = 1, pct = false } = opts
  return {
    id: key,
    accessorKey: key,
    header,
    cell: ({ getValue }) => {
      const v = getValue() as number | null | undefined
      return pct ? fmtPct(v) : fmt(v, decimals)
    },
  }
}

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

// -- Column sets ---------------------------------------------------------------

const BASIC_COLS: ColumnDef<TeamStat, unknown>[] = [
  nameCol(),
  numCol('total_games', 'PJ', { decimals: 0 }),
  numCol('games_home', 'L', { decimals: 0 }),
  numCol('games_away', 'V', { decimals: 0 }),
  numCol('points_per_game', 'PPP'),
  numCol('points_against_per_game', 'PPC'),
  numCol('fg2_percentage', '%T2', { pct: true }),
  numCol('fg3_percentage', '%T3', { pct: true }),
  numCol('ft_percentage', '%TL', { pct: true }),
  numCol('rebounds_per_game', 'Reb'),
  numCol('offensive_rebounds_per_game', 'RO'),
  numCol('defensive_rebounds_per_game', 'RD'),
  numCol('assists_per_game', 'Ast'),
  numCol('steals_per_game', 'Rob'),
  numCol('turnovers_per_game', 'Perd'),
  numCol('blocks_per_game', 'Tap'),
  numCol('possessions_per_game', 'Pos'),
]

const ADVANCED_COLS: ColumnDef<TeamStat, unknown>[] = [
  nameCol(),
  numCol('total_games', 'PJ', { decimals: 0 }),
  numCol('offensive_rating', 'OER'),
  numCol('defensive_rating', 'DER'),
  numCol('net_rating', 'Net'),
  numCol('efg_percentage', 'eFG%', { pct: true }),
  numCol('true_shooting', 'TS%', { pct: true }),
  numCol('three_point_rate', '3Pr%', { pct: true }),
  numCol('free_throw_rate', 'FTr%', { pct: true }),
  numCol('assist_fg_rate', 'AST/FG', { pct: true }),
  numCol('assist_rate', 'AST%', { pct: true }),
  numCol('turnover_rate', 'TOV%', { pct: true }),
  numCol('steal_rate', 'ROB%', { pct: true }),
  numCol('block_rate', 'TAP%', { pct: true }),
  numCol('offensive_rebound_rate', 'ORB%', { pct: true }),
  numCol('defensive_rebound_rate', 'RD%', { pct: true }),
]

/** Columns where lower is better (reversed Q colouring) */
const REVERSE_BASIC = ['points_against_per_game', 'turnovers_per_game']
const REVERSE_ADV   = ['defensive_rating', 'turnover_rate']

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

  const highlights = useMemo(() => ({
    oer: mean(teamRows, 'offensive_rating'),
    der: mean(teamRows, 'defensive_rating'),
    net: mean(teamRows, 'net_rating'),
    ppg: mean(teamRows, 'points_per_game'),
  }), [teamRows])

  const activeData = tab === 'rivals' ? rivalRows : teamRows
  const activeCols = tab === 'advanced' ? ADVANCED_COLS : BASIC_COLS
  const activeRev  = tab === 'advanced' ? REVERSE_ADV   : REVERSE_BASIC

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

        {/* Trend comparison panel — visible only when a date filter is active */}
        {hasDateFilter && (seasonData?.team_stats?.length ?? 0) > 0 && (
          <div className="card p-4">
            <h2 className="text-sm font-semibold text-ink-muted uppercase tracking-wider mb-3">
              Tendencia vs temporada completa
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
              {teamRows.map(recent => {
                const season = seasonByName[recent.team_name]
                if (!season) return null
                return (
                  <div
                    key={recent.team_name}
                    className="flex items-center justify-between p-2 rounded bg-surface-muted border border-surface-border gap-2"
                  >
                    <span className="text-xs font-medium text-ink-primary truncate flex-1">
                      {recent.team_name}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                      <TrendBadge recent={recent.offensive_rating}  season={season.offensive_rating}  />
                      <TrendBadge recent={recent.defensive_rating}  season={season.defensive_rating}  reverse />
                      <TrendBadge recent={recent.points_per_game}   season={season.points_per_game}   />
                    </div>
                  </div>
                )
              })}
            </div>
            <p className="text-xs text-ink-muted mt-2">OER · DER (inv.) · PPG</p>
          </div>
        )}

        {/* Highlight stat cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="OER Medio" value={fmt(highlights.oer)} accent="green" />
          <StatCard label="DER Medio" value={fmt(highlights.der)} accent="blue"  />
          <StatCard label="Net Medio" value={fmt(highlights.net)} accent={highlights.net >= 0 ? 'green' : 'red'} />
          <StatCard label="PPP Medio" value={fmt(highlights.ppg)} />
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-surface-border">
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
