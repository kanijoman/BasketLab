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
import { Users, ChevronDown } from 'lucide-react'

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
  opts: { decimals?: number; pct?: boolean } = {},
  consistencyByPlayerId: ConsistencyMap | null = null,
): ColumnDef<PlayerStat, unknown> {
  const { decimals = 1, pct = false } = opts
  return {
    id: key,
    accessorKey: key,
    header: tippedHeader(header),
    cell: ({ getValue, row }) => {
      const v = getValue() as number | null | undefined
      const formatted = pct ? fmtPct(v) : fmt(v, decimals)
      const cvEntry = consistencyByPlayerId?.[(row.original as PlayerStat).player_id]?.[key]
      if (!cvEntry) return formatted
      return (
        <span className="inline-flex items-center gap-1.5">
          <span>{formatted}</span>
          <CVBadge entry={cvEntry} />
        </span>
      )
    },
  }
}

function nameCol(): ColumnDef<PlayerStat, unknown> {
  return {
    id: 'player_name',
    accessorKey: 'player_name',
    header: 'Jugador',
    cell: ({ getValue }) => (
      <span className="font-medium text-ink-primary whitespace-nowrap">{getValue() as string}</span>
    ),
  }
}

function teamCol(): ColumnDef<PlayerStat, unknown> {
  return {
    id: 'team_name',
    accessorKey: 'team_name',
    header: 'Equipo',
    cell: ({ getValue }) => (
      <span className="text-ink-secondary text-xs whitespace-nowrap">{getValue() as string}</span>
    ),
  }
}

// -- Column sets ---------------------------------------------------------------

// -- Column sets (factories — receive consistency map at render time) ---------

function buildStatsCols(cv: ConsistencyMap | null): ColumnDef<PlayerStat, unknown>[] {
  return [
    nameCol(),
    teamCol(),
    buildNumCol('games_played', 'PJ', { decimals: 0 }),
    buildNumCol('minutes_per_game',            'MIN',  {},              cv),
    buildNumCol('points_per_game',             'PTS',  {},              cv),
    buildNumCol('rebounds_per_game',           'REB',  {},              cv),
    buildNumCol('offensive_rebounds_per_game', 'RO',   {},              cv),
    buildNumCol('defensive_rebounds_per_game', 'RD',   {},              cv),
    buildNumCol('assists_per_game',            'AST',  {},              cv),
    buildNumCol('steals_per_game',             'ROB',  {},              cv),
    buildNumCol('turnovers_per_game',          'PER',  {},              cv),
    buildNumCol('blocks_per_game',             'TAP',  {},              cv),
    buildNumCol('fouls_per_game',              'FP',   {},              cv),
    buildNumCol('valoracion_per_game',         'VAL',  {},              cv),
    buildNumCol('pllss_per_game',              '+/-',  {},              cv),
  ]
}

function buildShootingCols(cv: ConsistencyMap | null): ColumnDef<PlayerStat, unknown>[] {
  return [
    nameCol(),
    teamCol(),
    buildNumCol('games_played', 'PJ', { decimals: 0 }),
    buildNumCol('minutes_per_game', 'MIN',  {},               cv),
    buildNumCol('fg1_percentage',   '%TL',  { pct: true },    cv),
    buildNumCol('fg2_percentage',   '%T2',  { pct: true },    cv),
    buildNumCol('fg3_percentage',   '%T3',  { pct: true },    cv),
    buildNumCol('points_per_game',  'PTS',  {},               cv),
    buildNumCol('total_p2m', 'T2M', { decimals: 0 }),
    buildNumCol('total_p2a', 'T2I', { decimals: 0 }),
    buildNumCol('total_p3m', 'T3M', { decimals: 0 }),
    buildNumCol('total_p3a', 'T3I', { decimals: 0 }),
  ]
}

const REVERSE_STATS = ['turnovers_per_game', 'fouls_per_game']

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
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">Porcentajes de tiro</h3>
          <StatRow label="% Tiros libres"   value={fmtPct(player.fg1_percentage)} />
          <StatRow label="% Tiros de 2"     value={fmtPct(player.fg2_percentage)} />
          <StatRow label="% Triples"        value={fmtPct(player.fg3_percentage)} />
        </div>

        <div>
          <h3 className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">Totales temporada</h3>
          <StatRow label="Puntos totales"   value={fmt(player.total_pts, 0)} />
          <StatRow label="Minutos totales"  value={fmt(player.total_minutes, 0)} />
          <StatRow label="Minutos / partido (real)" value={fmt(player.total_minutes != null && player.games_played ? player.total_minutes / player.games_played : undefined)} />
        </div>
      </div>
    </SlideDrawer>
  )
}

// -- Tabs ---------------------------------------------------------------------

const TABS = [
  { id: 'stats',    label: 'Stats'    },
  { id: 'shooting', label: 'Tiro'    },
] as const
type TabId = (typeof TABS)[number]['id']

// -- Component -----------------------------------------------------------------

export default function PlayerStatsPage() {
  const { collection } = useCollection()
  const filters = useFilters()
  const [tab, setTab]           = useState<TabId>('stats')
  const [teamFilter, setTeamFilter] = useState('')
  const [selected, setSelected]     = useState<PlayerStat | null>(null)

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

  const activeCols = useMemo(
    () => tab === 'shooting' ? buildShootingCols(consistencyByPlayerId) : buildStatsCols(consistencyByPlayerId),
    [tab, consistencyByPlayerId],
  )
  const quartiles  = useMemo(() => buildPlayerQuartiles(players, activeCols), [players, activeCols])

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
        {hasDateFilter && seasonPlayers.length > 0 && (() => {
          // Build comparison list for currently visible players
          const compared = players
            .map(p => ({ p, s: seasonById[p.player_id] }))
            .filter(({ s }) => s != null && (s.points_per_game ?? 0) > 0) as Array<{ p: PlayerStat; s: PlayerStat }>

          // If no team filter, show top-3 improved and top-3 declined by PPG %
          const sorted = [...compared].sort((a, b) => {
            const da = (a.p.points_per_game ?? 0) - (a.s.points_per_game ?? 0)
            const db = (b.p.points_per_game ?? 0) - (b.s.points_per_game ?? 0)
            return db - da
          })
          const display = teamFilter ? compared : [
            ...sorted.slice(0, 3),
            ...sorted.slice(-3).reverse(),
          ]
          if (display.length === 0) return null

          return (
            <div className="card p-4">
              <h2 className="text-sm font-semibold text-ink-muted uppercase tracking-wider mb-3">
                Tendencia vs temporada completa
                {!teamFilter && <span className="ml-2 normal-case font-normal">(top +3 / top −3 por PPG)</span>}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {display.map(({ p, s }) => (
                  <div
                    key={p.player_id}
                    className="flex items-center justify-between p-2 rounded bg-surface-muted border border-surface-border gap-2"
                  >
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="text-xs font-medium text-ink-primary truncate">{p.player_name}</span>
                      <span className="text-[10px] text-ink-muted truncate">{p.team_name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <TrendBadge recent={p.points_per_game}    season={s.points_per_game}    />
                      <TrendBadge recent={p.rebounds_per_game}  season={s.rebounds_per_game}  />
                      <TrendBadge recent={p.assists_per_game}   season={s.assists_per_game}   />
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-ink-muted mt-2">PPG · REB · AST</p>
            </div>
          )
        })()}

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

        {/* Table — clicking a row opens the player drawer */}
        <DataTable
          columns={activeCols}
          data={players}
          quartiles={quartiles}
          reverseColumns={tab === 'stats' ? REVERSE_STATS : []}
          loading={isLoading}
          searchable
          searchPlaceholder="Buscar jugador…"
          exportOptions={{
            filename:   `jugadores_${tab}_${collection.name}`,
            pdfTitle:   `Estadísticas de Jugadores — ${tab}`,
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

