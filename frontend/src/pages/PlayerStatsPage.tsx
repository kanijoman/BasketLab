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
  opts: { decimals?: number; pct?: boolean } = {},
  consistencyByPlayerId: ConsistencyMap | null = null,
  thresholds: [number, number] = [50, 100],
  cvKey?: string,
): ColumnDef<PlayerStat, unknown> {
  const { decimals = 1, pct = false } = opts
  return {
    id: key,
    accessorKey: key,
    header: tippedHeader(header),
    cell: ({ getValue, row }) => {
      const v = getValue() as number | null | undefined
      const formatted = pct ? fmtPct(v) : fmt(v, decimals)
      const cvEntry = consistencyByPlayerId?.[(row.original as PlayerStat).player_id]?.[cvKey ?? key]
      if (!cvEntry) return formatted
      return (
        <span className="inline-flex items-center gap-1.5">
          <span>{formatted}</span>
          <CVBadge entry={cvEntry} thresholds={thresholds} />
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
    buildNumCol('games_played',              'PJ',  { decimals: 0 }),
    buildNumCol('minutes_per_game',          'MIN', {},              cv, PLAYER_CV),
    buildNumCol('points_per_game',           'PTS', {},              cv, PLAYER_CV),
    buildNumCol('rebounds_per_game',         'REB', {},              cv, PLAYER_CV),
    buildNumCol('offensive_rebounds_per_game','RO', {},              cv, PLAYER_CV),
    buildNumCol('defensive_rebounds_per_game','RD', {},              cv, PLAYER_CV),
    buildNumCol('assists_per_game',          'AST', {},              cv, PLAYER_CV),
    buildNumCol('steals_per_game',           'ROB', {},              cv, PLAYER_CV),
    buildNumCol('turnovers_per_game',        'PER', {},              cv, PLAYER_CV),
    buildNumCol('blocks_per_game',           'TAP', {},              cv, PLAYER_CV),
    buildNumCol('fouls_per_game',            'FP',  {},              cv, PLAYER_CV),
    buildNumCol('valoracion_per_game',       'VAL', {},              cv, PLAYER_CV),
    buildNumCol('pllss_per_game',            '+/-', {},              cv, PLAYER_CV),
    buildNumCol('fg1_percentage',            '%TL', { pct: true },   cv, PLAYER_CV),
    buildNumCol('fg2_percentage',            '%T2', { pct: true },   cv, PLAYER_CV),
    buildNumCol('fg3_percentage',            '%T3', { pct: true },   cv, PLAYER_CV),
  ]
}

function buildAdvancedCols(cv: ConsistencyMap | null): ColumnDef<PlayerStat, unknown>[] {
  return [
    nameCol(),
    teamLogoCol(),
    buildNumCol('games_played',      'PJ',     { decimals: 0 }),
    buildNumCol('minutes_per_game',  'MIN',    {},              cv, PLAYER_CV),
    buildNumCol('usage_pct',         'Usg%',   {},              cv, PLAYER_CV),
    buildNumCol('orating',           'ORtg',   {}),
    buildNumCol('drating',           'DRtg',   {}),
    buildNumCol('net_rtg',           'NetRtg', {}),
    buildNumCol('efg_percentage',    'eFG%',   { pct: true },   cv, PLAYER_CV),
    buildNumCol('true_shooting',     'TS%',    { pct: true },   cv, PLAYER_CV),
    buildNumCol('free_throw_rate',   'FTr',    { pct: true },   cv, PLAYER_CV),
    buildNumCol('three_point_rate',  '3Pr',    { pct: true },   cv, PLAYER_CV),
    buildNumCol('ast_pct',           '%AST',   {},              cv, PLAYER_CV),
    buildNumCol('tov_pct_adv',       '%TO',    {},              cv, PLAYER_CV, 'turnover_rate'),
    buildNumCol('stl_pct',           '%ROB',   {},              cv, PLAYER_CV),
    buildNumCol('blk_pct',           '%TAP',   {},              cv, PLAYER_CV),
    buildNumCol('drb_pct',           '%RD',    {},              cv, PLAYER_CV),
    buildNumCol('orb_pct',           '%RO',    {},              cv, PLAYER_CV),
    buildNumCol('pie',               'PIE%',   {}),
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
    buildNumCol('games_played',    'PJ',  { decimals: 0 }),
    buildNumCol('minutes_per_game','MIN', {}),
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

