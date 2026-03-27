/**
 * PlayerStatsPage — season statistics for all players in a collection.
 *
 * Features:
 * - Team filter dropdown (derived from data)
 * - Tabs: Stats | Tiro
 * - Client-side quartile colouring
 * - SlideDrawer profile panel on row click
 * - Export: CSV / PNG / PDF via DataTable
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { Users, ChevronDown, Info } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getPlayerStats, getPlayerConsistency, type PlayerStat, type TeamFilters, type ConsistencyMap } from '@/api/client'
import { fmt, fmtPct } from '@/lib/utils'
import PageTransition from '@/components/ui/PageTransition'
import FilterBar, { useFilters } from '@/components/ui/FilterBar'
import DataTable, { type QuartileMap } from '@/components/ui/DataTable'
import SlideDrawer from '@/components/ui/SlideDrawer'
import TrendBadge from '@/components/ui/TrendBadge'
import CVBadge from '@/components/ui/CVBadge'
import { tippedHeader } from '@/components/ui/Tooltip'

// -- Column helpers ------------------------------------------------------------

function buildNumCol(
  key: string,
  header: string,
  opts: { decimals?: number; pct?: boolean; size?: number } = {},
  consistencyByPlayerId: ConsistencyMap | null = null,
  thresholds: [number, number] = [50, 100],
  cvKey?: string,
): ColumnDef<PlayerStat, unknown> {
  const { decimals = 1, pct = false, size = 56 } = opts
  return {
    id: key,
    accessorKey: key,
    size,
    header: tippedHeader(header),
    cell: ({ getValue, row }) => {
      const v = getValue() as number | null | undefined
      const formatted = pct ? fmtPct(v) : fmt(v, decimals)
      const cvEntry = consistencyByPlayerId?.[(row.original as PlayerStat).player_id]?.[cvKey ?? key]
      if (!cvEntry) return formatted
      return (
        <span className="inline-flex items-center gap-1.5">
          <span>{formatted}</span>
          <span className="hidden group-hover:inline-flex">
            <CVBadge entry={cvEntry} thresholds={thresholds} />
          </span>
        </span>
      )
    },
  }
}

function nameCol(): ColumnDef<PlayerStat, unknown> {
  return {
    id: 'player_name',
    accessorKey: 'player_name',
    size: 140,
    header: 'Jugador',
    cell: ({ getValue }) => (
      <span className="font-medium text-ink-primary whitespace-nowrap">{getValue() as string}</span>
    ),
  }
}

function TeamLogoCell({ teamId, teamName }: { teamId?: string; teamName: string }) {
  const [failed, setFailed] = useState(false)
  if (teamId && !failed) {
    const url = `https://imagenes.feb.es/imagen.aspx?i=${teamId}&ti=1`
    return (
      <img
        src={url}
        alt={teamName}
        title={teamName}
        className="h-7 max-w-[42px] object-contain mx-auto block"
        onError={() => setFailed(true)}
      />
    )
  }
  return <span className="text-ink-secondary text-xs" title={teamName}>{teamName.slice(0, 3).toUpperCase()}</span>
}

function teamLogoCol(): ColumnDef<PlayerStat, unknown> {
  return {
    id: 'team_name',
    accessorKey: 'team_name',
    size: 42,
    header: '',
    cell: ({ getValue, row }) => (
      <TeamLogoCell teamId={row.original.team_id} teamName={getValue() as string} />
    ),
  }
}

// -- Column sets (factories — receive consistency map at render time) ---------

const PLAYER_CV: [number, number] = [50, 100]

function buildBasicCols(cv: ConsistencyMap | null): ColumnDef<PlayerStat, unknown>[] {
  return [
    nameCol(),
    teamLogoCol(),
    buildNumCol('games_played',              'PJ',  { decimals: 0, size: 44 }),
    buildNumCol('minutes_per_game',          'MIN', { size: 52 },  cv, PLAYER_CV),
    buildNumCol('points_per_game',           'PTS', { size: 52 },  cv, PLAYER_CV),
    buildNumCol('rebounds_per_game',         'REB', {},            cv, PLAYER_CV),
    buildNumCol('offensive_rebounds_per_game','RO', { size: 48 },  cv, PLAYER_CV),
    buildNumCol('defensive_rebounds_per_game','RD', { size: 48 },  cv, PLAYER_CV),
    buildNumCol('assists_per_game',          'AST', {},            cv, PLAYER_CV),
    buildNumCol('steals_per_game',           'ROB', {},            cv, PLAYER_CV),
    buildNumCol('turnovers_per_game',        'PER', {},            cv, PLAYER_CV),
    buildNumCol('blocks_per_game',           'TAP', {},            cv, PLAYER_CV),
    buildNumCol('fouls_per_game',            'FP',  { size: 48 },  cv, PLAYER_CV),
    buildNumCol('valoracion_per_game',       'VAL', {},            cv, PLAYER_CV),
    buildNumCol('pllss_per_game',            '+/-', {},            cv, PLAYER_CV),
    buildNumCol('fg1_percentage',            '%TL', { pct: true, size: 58 }, cv, PLAYER_CV),
    buildNumCol('fg2_percentage',            '%T2', { pct: true, size: 58 }, cv, PLAYER_CV),
    buildNumCol('fg3_percentage',            '%T3', { pct: true, size: 58 }, cv, PLAYER_CV),
  ]
}

function buildAdvancedCols(cv: ConsistencyMap | null): ColumnDef<PlayerStat, unknown>[] {
  return [
    nameCol(),
    teamLogoCol(),
    buildNumCol('games_played',      'PJ',     { decimals: 0, size: 44 }),
    buildNumCol('minutes_per_game',  'MIN',    { size: 52 },  cv, PLAYER_CV),
    buildNumCol('usage_pct',         'Usg%',   { size: 58 },  cv, PLAYER_CV),
    buildNumCol('orating',           'ORtg',   { size: 58 }),
    buildNumCol('drating',           'DRtg',   { size: 58 }),
    buildNumCol('net_rtg',           'NetRtg', { size: 62 }),
    buildNumCol('efg_percentage',    'eFG%',   { pct: true, size: 60 }, cv, PLAYER_CV),
    buildNumCol('true_shooting',     'TS%',    { pct: true, size: 56 }, cv, PLAYER_CV),
    buildNumCol('free_throw_rate',   'FTr',    { pct: true, size: 52 }, cv, PLAYER_CV),
    buildNumCol('three_point_rate',  '3Pr',    { pct: true, size: 52 }, cv, PLAYER_CV),
    buildNumCol('ast_pct',           '%AST',   { size: 58 },  cv, PLAYER_CV),
    buildNumCol('tov_pct_adv',       '%TO',    { size: 52 },  cv, PLAYER_CV, 'turnover_rate'),
    buildNumCol('stl_pct',           '%ROB',   { size: 56 },  cv, PLAYER_CV),
    buildNumCol('blk_pct',           '%TAP',   { size: 56 },  cv, PLAYER_CV),
    buildNumCol('drb_pct',           '%RD',    { size: 52 },  cv, PLAYER_CV),
    buildNumCol('orb_pct',           '%RO',    { size: 52 },  cv, PLAYER_CV),
    buildNumCol('pie',               'PIE%',   { size: 58 }),
  ]
}

function projNum(
  id: string,
  header: string,
  statKey: keyof PlayerStat,
  reverse = false,
): ColumnDef<PlayerStat, unknown> {
  return {
    id,
    size: 60,
    header: tippedHeader(header),
    accessorFn: (row: PlayerStat) => {
      const mpg = row.minutes_per_game
      if (!mpg || mpg < 10) return null
      const val = row[statKey] as number | null | undefined
      if (val == null) return null
      return (val / mpg) * 30
    },
    cell: ({ getValue }) => fmt(getValue() as number | null | undefined),
    enableSorting: true,
    meta: { reverse },
  }
}

function buildProjectionQuartiles(data: PlayerStat[]): QuartileMap {
  const projPairs: Array<[string, keyof PlayerStat, boolean]> = [
    ['pts_proj',   'points_per_game',    false],
    ['reb_proj',   'rebounds_per_game',  false],
    ['ast_proj',   'assists_per_game',   false],
    ['rob_proj',   'steals_per_game',    false],
    ['per_proj',   'turnovers_per_game', true ],
    ['tap_proj',   'blocks_per_game',    false],
    ['val_proj',   'valoracion_per_game',false],
    ['pllss_proj', 'pllss_per_game',     false],
  ]
  const map: QuartileMap = {}
  for (const [id, statKey] of projPairs) {
    const vals = data
      .filter(p => (p.minutes_per_game ?? 0) >= 10)
      .map(p => {
        const v = p[statKey] as number | null | undefined
        if (v == null || !p.minutes_per_game) return null
        return (v / p.minutes_per_game) * 30
      })
      .filter((v): v is number => v !== null && !Number.isNaN(v))
      .sort((a, b) => a - b)
    if (vals.length >= 4) {
      const q = (p: number) => {
        const idx = (vals.length - 1) * p
        const lo = Math.floor(idx), hi = Math.ceil(idx)
        return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)
      }
      map[id] = [q(0.25), q(0.5), q(0.75)]
    }
  }
  return map
}

function buildProjectionCols(): ColumnDef<PlayerStat, unknown>[] {
  return [
    nameCol(),
    teamLogoCol(),
    buildNumCol('games_played',    'PJ',  { decimals: 0, size: 44 }),
    buildNumCol('minutes_per_game','MIN', { size: 52 }),
    projNum('pts_proj',   'PTS×30', 'points_per_game'),
    projNum('reb_proj',   'REB×30', 'rebounds_per_game'),
    projNum('ast_proj',   'AST×30', 'assists_per_game'),
    projNum('rob_proj',   'ROB×30', 'steals_per_game'),
    projNum('per_proj',   'PER×30', 'turnovers_per_game', true),
    projNum('tap_proj',   'TAP×30', 'blocks_per_game'),
    projNum('val_proj',   'VAL×30', 'valoracion_per_game'),
    projNum('pllss_proj', '+/-×30', 'pllss_per_game'),
  ]
}

// -- Client-side quartile computation -----------------------------------------

function computeColQuartile(data: PlayerStat[], key: string): [number, number, number] {
  const vals = data
    .map(d => d[key] as number | undefined)
    .filter((v): v is number => typeof v === 'number' && !Number.isNaN(v))
    .sort((a, b) => a - b)
  if (vals.length < 4) return [0, 0, 0]
  const q = (p: number) => {
    const idx = (vals.length - 1) * p
    const lo = Math.floor(idx)
    const hi = Math.ceil(idx)
    return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)
  }
  return [q(0.25), q(0.5), q(0.75)]
}

function buildPlayerQuartiles(data: PlayerStat[], cols: ColumnDef<PlayerStat, unknown>[]): QuartileMap {
  const map: QuartileMap = {}
  for (const c of cols) {
    const key = (c as { accessorKey?: string }).accessorKey
    if (key && key !== 'player_name' && key !== 'team_name') {
      map[key] = computeColQuartile(data, key)
    }
  }
  return map
}

// -- Player Drawer -------------------------------------------------------------

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-center py-1.5 border-b border-surface-border/50">
      <span className="text-xs text-ink-muted">{label}</span>
      <span className="text-sm font-medium text-ink-primary tabular-nums">{value}</span>
    </div>
  )
}

function PlayerDrawer({ player, onClose }: { player: PlayerStat; onClose: () => void }) {
  return (
    <SlideDrawer open onClose={onClose} title={player.player_name} size="md">
      <div className="space-y-4 p-5">
        <p className="text-sm text-brand-400 font-medium">{player.team_name}</p>

        <div>
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">Por partido</h3>
          <StatRow label="Partidos jugados" value={fmt(player.games_played, 0)} />
          <StatRow label="Minutos / partido" value={fmt(player.minutes_per_game)} />
          <StatRow label="Puntos / partido"  value={fmt(player.points_per_game)} />
          <StatRow label="Rebotes / partido" value={fmt(player.rebounds_per_game)} />
          <StatRow label="Reb. ofensivos / partido" value={fmt(player.offensive_rebounds_per_game)} />
          <StatRow label="Reb. defensivos / partido" value={fmt(player.defensive_rebounds_per_game)} />
          <StatRow label="Asistencias / partido" value={fmt(player.assists_per_game)} />
          <StatRow label="Robos / partido"   value={fmt(player.steals_per_game)} />
          <StatRow label="Pérdidas / partido" value={fmt(player.turnovers_per_game)} />
          <StatRow label="Tapones / partido" value={fmt(player.blocks_per_game)} />
          <StatRow label="Faltas / partido"  value={fmt(player.fouls_per_game)} />
          <StatRow label="Valoración / partido" value={fmt(player.valoracion_per_game)} />
          <StatRow label="+/- por partido"   value={fmt(player.pllss_per_game)} />
        </div>

        <div>
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">Avanzado</h3>
          <StatRow label="eFG%"              value={fmtPct(player.efg_percentage)} />
          <StatRow label="TS%"               value={fmtPct(player.true_shooting)} />
          <StatRow label="Tasa TL (FTr)"    value={fmtPct(player.free_throw_rate)} />
          <StatRow label="Tasa triples (3Pr)" value={fmtPct(player.three_point_rate)} />
          <StatRow label="TOV%"              value={fmtPct(player.turnover_rate)} />
        </div>

        <div>
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">Porcentajes de tiro</h3>
          <StatRow label="% Tiros libres"   value={fmtPct(player.fg1_percentage)} />
          <StatRow label="% Tiros de 2"     value={fmtPct(player.fg2_percentage)} />
          <StatRow label="% Triples"        value={fmtPct(player.fg3_percentage)} />
        </div>

        <div>
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">Totales temporada</h3>
          <StatRow label="Puntos totales"   value={fmt(player.total_pts, 0)} />
          <StatRow label="Minutos totales"  value={fmt(player.total_minutes, 0)} />
        </div>
      </div>
    </SlideDrawer>
  )
}

// -- Available stats for the trend comparison panel -------------------------

const TREND_STAT_GROUPS: Array<{
  group: string
  options: Array<{ key: keyof PlayerStat; label: string; reverse?: boolean }>
}> = [
  {
    group: 'Básico',
    options: [
      { key: 'points_per_game',              label: 'PTS' },
      { key: 'rebounds_per_game',            label: 'REB' },
      { key: 'offensive_rebounds_per_game',  label: 'RO' },
      { key: 'defensive_rebounds_per_game',  label: 'RD' },
      { key: 'assists_per_game',             label: 'AST' },
      { key: 'steals_per_game',              label: 'ROB' },
      { key: 'turnovers_per_game',           label: 'PÉR', reverse: true },
      { key: 'blocks_per_game',              label: 'TAP' },
      { key: 'fouls_per_game',               label: 'FP',  reverse: true },
      { key: 'valoracion_per_game',          label: 'VAL' },
      { key: 'pllss_per_game',               label: '+/-' },
      { key: 'minutes_per_game',             label: 'MIN' },
    ],
  },
  {
    group: 'Tiro',
    options: [
      { key: 'fg1_percentage',  label: '%TL' },
      { key: 'fg2_percentage',  label: '%T2' },
      { key: 'fg3_percentage',  label: '%T3' },
      { key: 'efg_percentage',  label: 'eFG%' },
      { key: 'true_shooting',   label: 'TS%' },
      { key: 'free_throw_rate', label: 'FTr' },
      { key: 'three_point_rate',label: '3Pr' },
    ],
  },
  {
    group: 'Avanzado',
    options: [
      { key: 'usage_pct',    label: 'Usg%' },
      { key: 'orating',      label: 'ORtg' },
      { key: 'drating',      label: 'DRtg', reverse: true },
      { key: 'net_rtg',      label: 'Net' },
      { key: 'ast_pct',      label: '%AST' },
      { key: 'tov_pct_adv',  label: '%TO',  reverse: true },
      { key: 'stl_pct',      label: '%ROB' },
      { key: 'blk_pct',      label: '%TAP' },
      { key: 'orb_pct',      label: '%RO' },
      { key: 'drb_pct',      label: '%RD' },
      { key: 'pie',          label: 'PIE%' },
    ],
  },
]

/** Flat list used for lookups */
const TREND_STAT_OPTIONS = TREND_STAT_GROUPS.flatMap(g => g.options)

// -- Tabs ---------------------------------------------------------------------

const TABS = [
  { id: 'basic',      label: 'Básico'     },
  { id: 'advanced',   label: 'Avanzado'   },
  { id: 'projection', label: 'Proyección' },
] as const
type TabId = (typeof TABS)[number]['id']

// -- Component -----------------------------------------------------------------

export default function PlayerStatsPage() {
  const { collection } = useCollection()
  const filters = useFilters()
  const [tab, setTab]           = useState<TabId>('basic')
  const [teamFilter, setTeamFilter] = useState('')
  const [selected, setSelected]     = useState<PlayerStat | null>(null)
  const [trendStats, setTrendStats] = useState<Array<keyof PlayerStat>>(
    ['points_per_game', 'rebounds_per_game', 'assists_per_game'],
  )

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

  const { data: seasonPlayers = [] } = useQuery({
    queryKey:  ['player-stats-season', collection?.name, baselineFilters],
    queryFn:   () => getPlayerStats(collection!.name, baselineFilters),
    enabled:   Boolean(collection) && hasDateFilter,
    staleTime: 10 * 60_000,
  })

  const { data: rawPlayers = [], isLoading } = useQuery({
    queryKey: ['player-stats', collection?.name, apiFilters],
    queryFn:  () => getPlayerStats(collection!.name, apiFilters),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
  })

  const { data: consistencyRaw } = useQuery({
    queryKey:  ['player-consistency', collection?.name],
    queryFn:   () => getPlayerConsistency(collection!.name),
    enabled:   Boolean(collection),
    staleTime: 30 * 60_000,
  })
  const consistencyByPlayerId: ConsistencyMap | null = consistencyRaw ?? null

  const teamOptions = useMemo(
    () => [...new Set(rawPlayers.map(p => p.team_name))].sort(),
    [rawPlayers],
  )

  const players = useMemo(
    () => teamFilter ? rawPlayers.filter(p => p.team_name === teamFilter) : rawPlayers,
    [rawPlayers, teamFilter],
  )

  // Map player_id → full-season row for comparison
  const seasonById = useMemo(() => {
    const m: Record<string, PlayerStat> = {}
    for (const p of seasonPlayers) m[p.player_id] = p
    return m
  }, [seasonPlayers])

  // Players to show in the trend comparison panel
  const trendDisplay = useMemo(() => {
    if (!hasDateFilter || seasonPlayers.length === 0) return []
    const compared = players
      .map(p => ({ p, s: seasonById[p.player_id] }))
      .filter(({ s }) => s != null && (s.points_per_game ?? 0) > 0) as Array<{ p: PlayerStat; s: PlayerStat }>
    if (teamFilter) return compared
    const primaryKey = trendStats[0] ?? 'points_per_game'
    const primaryOpt = TREND_STAT_OPTIONS.find(o => o.key === primaryKey)
    const sorted = [...compared].sort((a, b) => {
      const da = ((a.p[primaryKey] as number) ?? 0) - ((a.s[primaryKey] as number) ?? 0)
      const db = ((b.p[primaryKey] as number) ?? 0) - ((b.s[primaryKey] as number) ?? 0)
      return primaryOpt?.reverse ? da - db : db - da
    })
    return [...sorted.slice(0, 3), ...sorted.slice(-3).reverse()]
  }, [hasDateFilter, seasonPlayers, players, seasonById, teamFilter, trendStats])

  const activeCols = useMemo(() => {
    if (tab === 'advanced')   return buildAdvancedCols(consistencyByPlayerId)
    if (tab === 'projection') return buildProjectionCols()
    return buildBasicCols(consistencyByPlayerId)
  }, [tab, consistencyByPlayerId])
  const reverseColumns = useMemo(() => {
    if (tab === 'advanced')   return ['drating', 'tov_pct_adv', 'turnover_rate']
    if (tab === 'projection') return ['per_proj']
    return ['turnovers_per_game', 'fouls_per_game']
  }, [tab])
  const quartiles = useMemo(() => {
    if (tab === 'projection') return buildProjectionQuartiles(players)
    return buildPlayerQuartiles(players, activeCols)
  }, [tab, players, activeCols])

  if (!collection) {
    return (
      <PageTransition>
        <p className="text-center text-ink-muted mt-16">Selecciona una colección para continuar.</p>
      </PageTransition>
    )
  }

  return (
    <PageTransition>
      <div className="space-y-4">

        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-ink-primary">Estadísticas de Jugadores</h1>
            <p className="text-sm text-ink-muted mt-0.5">{collection.label}</p>
          </div>
          <FilterBar showDate />
        </div>

        {/* Trend comparison panel — visible only when a date filter is active */}
        {hasDateFilter && trendDisplay.length > 0 && (
          <div className="card p-4 space-y-3">
            {/* Header + stat toggles */}
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-ink-muted uppercase tracking-wider">
                Tendencia vs temporada completa
              </h2>
              {TREND_STAT_GROUPS.map(({ group, options }) => (
                <div key={group} className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-semibold text-ink-muted uppercase tracking-wider w-14 shrink-0">{group}</span>
                  {options.map(opt => {
                    const active = trendStats.includes(opt.key)
                    return (
                      <button
                        key={String(opt.key)}
                        onClick={() =>
                          setTrendStats(prev =>
                            prev.includes(opt.key)
                              ? prev.filter(k => k !== opt.key)
                              : [...prev, opt.key],
                          )
                        }
                        className={[
                          'px-2 py-0.5 rounded text-[11px] font-medium border transition-colors',
                          active
                            ? 'bg-brand-500/20 border-brand-500/50 text-brand-400'
                            : 'bg-surface-muted border-surface-border text-ink-muted hover:text-ink-primary',
                        ].join(' ')}
                      >
                        {opt.label}
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
            {!teamFilter && trendStats.length > 0 && (
              <p className="text-xs text-ink-muted">
                Top +3 / Top −3 por {TREND_STAT_OPTIONS.find(o => o.key === trendStats[0])?.label ?? 'PTS'}
              </p>
            )}
            {trendStats.length === 0 ? (
              <p className="text-xs text-ink-muted italic">Selecciona al menos un estadístico para comparar.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {trendDisplay.map(({ p, s }) => (
                  <div
                    key={p.player_id}
                    className="flex items-center justify-between p-2 rounded bg-surface-muted border border-surface-border gap-2"
                  >
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="text-xs font-medium text-ink-primary truncate">{p.player_name}</span>
                      <span className="text-[10px] text-ink-muted truncate">{p.team_name}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 shrink-0">
                      {trendStats.map(key => {
                        const opt = TREND_STAT_OPTIONS.find(o => o.key === key)
                        if (!opt) return null
                        return (
                          <span key={String(key)} className="inline-flex items-center gap-0.5">
                            <span className="text-[10px] text-ink-muted font-medium">{opt.label}</span>
                            <TrendBadge
                              recent={p[key] as number}
                              season={s[key] as number}
                              reverse={opt.reverse}
                            />
                          </span>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Controls row */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Team filter */}
          <div className="relative">
            <select
              value={teamFilter}
              onChange={e => setTeamFilter(e.target.value)}
              className="select pr-8 pl-3 py-1.5 text-sm appearance-none"
            >
              <option value="">Todos los equipos</option>
              {teamOptions.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-muted pointer-events-none" />
          </div>

          <span className="text-xs text-ink-muted ml-auto">
            <Users className="inline w-3.5 h-3.5 mr-1" />
            {players.length} jugadores
          </span>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-surface-border">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={[
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px',
                tab === id
                  ? 'border-brand-500 text-brand-400'
                  : 'border-transparent text-ink-muted hover:text-ink-primary',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Projection methodology banner */}
        {tab === 'projection' && (
          <div className="flex items-start gap-3 rounded-md bg-blue-950/40 border border-blue-800/50 px-4 py-3 text-sm text-blue-200">
            <Info className="w-4 h-4 mt-0.5 shrink-0 text-blue-400" />
            <div className="space-y-0.5">
              <p className="font-semibold">Proyección estadística a 30 minutos</p>
              <p className="text-blue-300/80 text-xs">
                Escala las estadísticas de cada jugadora al equivalente de disputar 30 minutos por partido.
                Las jugadoras con menos de 10 minutos de media por partido no se incluyen en el cálculo.
              </p>
            </div>
          </div>
        )}

        {/* Table — clicking a row opens the player drawer */}
        <DataTable
          columns={activeCols}
          data={players}
          quartiles={quartiles}
          reverseColumns={reverseColumns}
          loading={isLoading}
          searchable
          searchPlaceholder="Buscar jugador…"
          exportOptions={{
            filename:   `jugadores_${tab}_${collection.name}`,
            pdfTitle:   `Estadísticas de Jugadores — ${tab === 'basic' ? 'Básico' : tab === 'advanced' ? 'Avanzado' : 'Proyección'}`,
            csvHeaders: activeCols.map(c => ({
              key:   String((c as { accessorKey?: string }).accessorKey ?? c.id ?? ''),
              label: String(c.header ?? ''),
            })),
            csvData: players,
          }}
          onRowClick={row => setSelected(row.original)}
        />

        {/* Player detail drawer */}
        {selected && (
          <PlayerDrawer player={selected} onClose={() => setSelected(null)} />
        )}

      </div>
    </PageTransition>
  )
}

