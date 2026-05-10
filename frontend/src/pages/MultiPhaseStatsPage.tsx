/**
 * MultiPhaseStatsPage — estadísticas combinadas de múltiples fases de temporada.
 *
 * Detecta automáticamente las colecciones hermanas (mismo torneo/temporada),
 * permite al usuario seleccionar cuáles incluir y muestra las estadísticas
 * acumuladas con la misma estructura que TeamStatsPage:
 *   Equipos → Básico | Avanzado
 *   Jugadores → tabla básica
 */
import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { BarChart2, Layers, Zap } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import {
  getSiblingCollections,
  getMultiTeamStats,
  getMultiPlayerStats,
  type TeamStat,
  type PlayerStat,
} from '@/api/client'
import { fmt, fmtPct } from '@/lib/utils'
import PageTransition from '@/components/ui/PageTransition'
import DataTable, { type QuartileMap } from '@/components/ui/DataTable'
import { tippedHeader } from '@/components/ui/Tooltip'

// ---------------------------------------------------------------------------
// Column metadata (mirrors TeamStatsPage ColDef)
// ---------------------------------------------------------------------------

interface ColDef {
  key: keyof TeamStat
  header: string
  decimals?: number
  pct?: boolean
  reverse?: boolean
  count?: boolean
  size?: number
}

const BASIC_COL_DEFS: ColDef[] = [
  { key: 'total_games',                 header: 'PJ',    decimals: 0, count: true, size: 44 },
  { key: 'points_per_game',             header: 'PPP',   size: 58 },
  { key: 'points_against_per_game',     header: 'PPC',   reverse: true, size: 58 },
  { key: 'fg2_percentage',              header: '%T2',   pct: true, size: 62 },
  { key: 'fg3_percentage',              header: '%T3',   pct: true, size: 62 },
  { key: 'ft_percentage',               header: '%TL',   pct: true, size: 62 },
  { key: 'rebounds_per_game',           header: 'Reb',   size: 56 },
  { key: 'offensive_rebounds_per_game', header: 'RO',    size: 48 },
  { key: 'defensive_rebounds_per_game', header: 'RD',    size: 48 },
  { key: 'assists_per_game',            header: 'Ast',   size: 48 },
  { key: 'steals_per_game',             header: 'Rob',   size: 48 },
  { key: 'turnovers_per_game',          header: 'Perd',  reverse: true, size: 52 },
  { key: 'blocks_per_game',             header: 'Tap',   size: 48 },
]

const ADVANCED_COL_DEFS: ColDef[] = [
  { key: 'total_games',            header: 'PJ',     decimals: 0, count: true, size: 44 },
  { key: 'possessions_per_game',   header: 'Pos',    size: 52 },
  { key: 'offensive_rating',       header: 'OER',    size: 56 },
  { key: 'defensive_rating',       header: 'DER',    reverse: true, size: 56 },
  { key: 'net_rating',             header: 'Net',    size: 56 },
  { key: 'efg_percentage',         header: 'eFG%',   pct: true, size: 62 },
  { key: 'true_shooting',          header: 'TS%',    pct: true, size: 58 },
  { key: 'three_point_rate',       header: '3Pr%',   pct: true, size: 58 },
  { key: 'free_throw_rate',        header: 'FTr%',   pct: true, size: 58 },
  { key: 'assist_fg_rate',         header: 'AST/FG', pct: true, size: 68 },
  { key: 'assist_rate',            header: 'AST%',   pct: true, size: 60 },
  { key: 'turnover_rate',          header: 'TOV%',   pct: true, reverse: true, size: 62 },
  { key: 'steal_rate',             header: 'ROB%',   pct: true, size: 62 },
  { key: 'block_rate',             header: 'TAP%',   pct: true, size: 62 },
  { key: 'offensive_rebound_rate', header: 'ORB%',   pct: true, size: 62 },
  { key: 'defensive_rebound_rate', header: 'RD%',    pct: true, size: 60 },
]

const REVERSE_BASIC = BASIC_COL_DEFS.filter(d => d.reverse).map(d => d.key as string)
const REVERSE_ADV   = ADVANCED_COL_DEFS.filter(d => d.reverse).map(d => d.key as string)

// ---------------------------------------------------------------------------
// Team column builders
// ---------------------------------------------------------------------------

function teamNameCol(): ColumnDef<TeamStat, unknown> {
  return {
    id: 'team_name',
    accessorKey: 'team_name',
    size: 150,
    header: 'Equipo',
    cell: ({ getValue }) => (
      <span className="font-medium text-ink-primary whitespace-nowrap">
        {getValue() as string}
      </span>
    ),
    enableSorting: true,
  }
}

function buildTeamCol(def: ColDef): ColumnDef<TeamStat, unknown> {
  const { key, header, decimals = 1, pct = false, size = 60 } = def
  return {
    id: key as string,
    accessorKey: key as string,
    size,
    header: tippedHeader(header),
    cell: ({ getValue }) => {
      const v = getValue() as number | null | undefined
      return pct ? fmtPct(v) : fmt(v, decimals)
    },
    enableSorting: true,
  }
}

function buildTeamCols(defs: ColDef[]): ColumnDef<TeamStat, unknown>[] {
  return [teamNameCol(), ...defs.map(buildTeamCol)]
}

// ---------------------------------------------------------------------------
// Player column builders
// ---------------------------------------------------------------------------

function playerNameCol(): ColumnDef<PlayerStat, unknown> {
  return {
    id: 'player_name',
    accessorKey: 'player_name',
    size: 160,
    header: 'Jugador',
    cell: ({ getValue }) => (
      <span className="font-medium text-ink-primary whitespace-nowrap">
        {getValue() as string}
      </span>
    ),
    enableSorting: true,
  }
}

function playerTeamCol(): ColumnDef<PlayerStat, unknown> {
  return {
    id: 'team_name',
    accessorKey: 'team_name',
    size: 130,
    header: 'Equipo',
    cell: ({ getValue }) => (
      <span className="text-ink-secondary whitespace-nowrap text-xs">
        {getValue() as string}
      </span>
    ),
    enableSorting: true,
  }
}

function buildPlayerNumCol(
  key: keyof PlayerStat,
  header: string,
  opts: { decimals?: number; pct?: boolean; size?: number } = {},
): ColumnDef<PlayerStat, unknown> {
  const { decimals = 1, pct = false, size = 56 } = opts
  return {
    id: key as string,
    accessorKey: key as string,
    size,
    header: tippedHeader(header),
    cell: ({ getValue }) => {
      const v = getValue() as number | null | undefined
      return pct ? fmtPct(v) : fmt(v, decimals)
    },
    enableSorting: true,
  }
}

const PLAYER_COLS: ColumnDef<PlayerStat, unknown>[] = [
  playerNameCol(),
  playerTeamCol(),
  buildPlayerNumCol('games_played',      'PJ',   { decimals: 0, size: 44 }),
  buildPlayerNumCol('minutes_per_game',  'MIN',  { size: 52 }),
  buildPlayerNumCol('points_per_game',   'PTS',  { size: 52 }),
  buildPlayerNumCol('rebounds_per_game', 'REB',  {}),
  buildPlayerNumCol('assists_per_game',  'AST',  {}),
  buildPlayerNumCol('steals_per_game',   'ROB',  {}),
  buildPlayerNumCol('turnovers_per_game','PER',  {}),
  buildPlayerNumCol('blocks_per_game',   'TAP',  {}),
  buildPlayerNumCol('fg2_percentage',    '%T2',  { pct: true, size: 58 }),
  buildPlayerNumCol('fg3_percentage',    '%T3',  { pct: true, size: 58 }),
  buildPlayerNumCol('valoracion_per_game','VAL', {}),
]

const PLAYER_ADV_COLS: ColumnDef<PlayerStat, unknown>[] = [
  playerNameCol(),
  playerTeamCol(),
  buildPlayerNumCol('games_played',              'PJ',   { decimals: 0, size: 44 }),
  buildPlayerNumCol('minutes_per_game',          'MIN',  { size: 52 }),
  buildPlayerNumCol('points_per_game',           'PTS',  { size: 52 }),
  buildPlayerNumCol('efg_percentage',            'eFG%', { pct: true, size: 60 }),
  buildPlayerNumCol('true_shooting',             'TS%',  { pct: true, size: 60 }),
  buildPlayerNumCol('free_throw_rate',           'FTr%', { pct: true, size: 58 }),
  buildPlayerNumCol('three_point_rate',          '3Pr%', { pct: true, size: 58 }),
  buildPlayerNumCol('turnover_rate',             'TOV%', { pct: true, size: 58 }),
  buildPlayerNumCol('assist_fg_rate',            'AST/FG%', { pct: true, size: 72 }),
  buildPlayerNumCol('offensive_rebound_rate',    'ORB%', { pct: true, size: 60 }),
  buildPlayerNumCol('defensive_rebound_rate',    'DRB%', { pct: true, size: 60 }),
  buildPlayerNumCol('offensive_rebounds_per_game','RO',  {}),
  buildPlayerNumCol('defensive_rebounds_per_game','RD',  {}),
]

const REVERSE_PLAYER_ADV = ['turnover_rate']

// ---------------------------------------------------------------------------
// Client-side quartile computation (no dedicated API endpoint for multi-phase)
// ---------------------------------------------------------------------------

function computeTeamQuartiles(data: TeamStat[], defs: ColDef[]): QuartileMap {
  const map: QuartileMap = {}
  for (const def of defs) {
    if (def.count) continue
    const key = def.key as string
    const vals = data
      .map(d => d[key] as number | undefined)
      .filter((v): v is number => typeof v === 'number' && !isNaN(v))
      .sort((a, b) => a - b)
    if (vals.length < 4) continue
    const q = (p: number) => {
      const idx = (vals.length - 1) * p
      const lo = Math.floor(idx), hi = Math.ceil(idx)
      return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)
    }
    map[key] = [q(0.25), q(0.5), q(0.75)]
  }
  return map
}

function computePlayerQuartiles(data: PlayerStat[]): QuartileMap {
  const map: QuartileMap = {}
  const numericKeys = [
    'games_played', 'minutes_per_game', 'points_per_game', 'rebounds_per_game',
    'assists_per_game', 'steals_per_game', 'turnovers_per_game', 'blocks_per_game',
    'fg2_percentage', 'fg3_percentage', 'valoracion_per_game',
    // advanced
    'efg_percentage', 'true_shooting', 'free_throw_rate', 'three_point_rate',
    'turnover_rate', 'assist_fg_rate', 'offensive_rebound_rate', 'defensive_rebound_rate',
    'offensive_rebounds_per_game', 'defensive_rebounds_per_game',
  ]
  for (const key of numericKeys) {
    const vals = data
      .map(d => d[key as keyof PlayerStat] as number | undefined)
      .filter((v): v is number => typeof v === 'number' && !isNaN(v))
      .sort((a, b) => a - b)
    if (vals.length < 4) continue
    const q = (p: number) => {
      const idx = (vals.length - 1) * p
      const lo = Math.floor(idx), hi = Math.ceil(idx)
      return vals[lo] + (vals[hi] - vals[lo]) * (idx - lo)
    }
    map[key] = [q(0.25), q(0.5), q(0.75)]
  }
  return map
}

// ---------------------------------------------------------------------------
// Collection multi-selector (pill buttons)
// ---------------------------------------------------------------------------

function CollectionPicker({
  all,
  selected,
  onChange,
}: {
  all: string[]
  selected: string[]
  onChange: (next: string[]) => void
}) {
  function toggle(name: string) {
    onChange(
      selected.includes(name)
        ? selected.filter(n => n !== name)
        : [...selected, name],
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {all.map(name => (
        <button
          key={name}
          onClick={() => toggle(name)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
            selected.includes(name)
              ? 'bg-brand-600/20 border-brand-500/60 text-brand-400'
              : 'border-surface-border text-ink-muted hover:text-ink-primary hover:border-surface-border/80'
          }`}
        >
          {name.split('_').slice(-1)[0] ?? name}
        </button>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type EntityTab = 'equipos' | 'jugadores'
type StatTab   = 'basic' | 'advanced'

const ENTITY_TABS = [
  { id: 'equipos',   label: 'Equipos' },
  { id: 'jugadores', label: 'Jugadores' },
] as const

const STAT_TABS = [
  { id: 'basic',    label: 'Básico',   Icon: BarChart2 },
  { id: 'advanced', label: 'Avanzado', Icon: Zap       },
] as const

export default function MultiPhaseStatsPage() {
  const { collection } = useCollection()
  const [selectedCollections, setSelectedCollections] = useState<string[]>([])
  const [entityTab,       setEntityTab]       = useState<EntityTab>('equipos')
  const [statTab,         setStatTab]         = useState<StatTab>('basic')
  const [playerStatTab,   setPlayerStatTab]   = useState<StatTab>('basic')

  const isFbcyl = Boolean(collection?.isFbcyl)

  // Sibling collections
  const { data: siblings = [], isLoading: loadingSiblings } = useQuery({
    queryKey: ['sibling-collections', collection?.name],
    queryFn:  () => getSiblingCollections(collection!.name),
    enabled:  Boolean(collection),
    staleTime: 5 * 60_000,
  })

  // Pre-select all siblings on first load
  useEffect(() => {
    if (siblings.length > 0 && selectedCollections.length === 0) {
      setSelectedCollections(siblings)
    }
  }, [siblings])  // eslint-disable-line react-hooks/exhaustive-deps

  // Combined team stats (only fetched when Equipos tab is active)
  const { data: teamData = [], isLoading: loadingTeams } = useQuery({
    queryKey: ['multi-team-stats', selectedCollections, isFbcyl],
    queryFn:  () => getMultiTeamStats(selectedCollections, isFbcyl),
    enabled:  selectedCollections.length > 0 && entityTab === 'equipos',
    staleTime: 5 * 60_000,
  })

  // Combined player stats (only fetched when Jugadores tab is active)
  const { data: playerData = [], isLoading: loadingPlayers } = useQuery({
    queryKey: ['multi-player-stats', selectedCollections, isFbcyl],
    queryFn:  () => getMultiPlayerStats(selectedCollections, isFbcyl),
    enabled:  selectedCollections.length > 0 && entityTab === 'jugadores',
    staleTime: 5 * 60_000,
  })

  const teamRows   = teamData   as TeamStat[]
  const playerRows = playerData as PlayerStat[]

  // Client-side quartiles (computed from merged data)
  const basicQuartiles    = useMemo(() => computeTeamQuartiles(teamRows, BASIC_COL_DEFS),    [teamRows])
  const advancedQuartiles = useMemo(() => computeTeamQuartiles(teamRows, ADVANCED_COL_DEFS), [teamRows])
  const playerQuartiles   = useMemo(() => computePlayerQuartiles(playerRows),                [playerRows])

  const teamCols      = useMemo(() => buildTeamCols(statTab === 'basic' ? BASIC_COL_DEFS : ADVANCED_COL_DEFS), [statTab])
  const teamQuartiles = statTab === 'basic' ? basicQuartiles : advancedQuartiles
  const reverseTeam   = statTab === 'basic' ? REVERSE_BASIC : REVERSE_ADV

  const isLoading = entityTab === 'equipos' ? loadingTeams : loadingPlayers

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
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-brand-400 shrink-0" />
          <div>
            <h1 className="text-xl font-bold text-ink-primary">Estadísticas Multifase</h1>
            <p className="text-xs text-ink-muted mt-0.5">Totales acumulados entre fases seleccionadas</p>
          </div>
        </div>

        {/* Phase selector */}
        {loadingSiblings ? (
          <div className="h-8 rounded-full bg-surface-border/40 w-48 animate-pulse" />
        ) : siblings.length === 0 ? (
          <p className="text-sm text-ink-secondary">
            No se encontraron colecciones hermanas para <strong>{collection.name}</strong>.
          </p>
        ) : (
          <div className="card p-4 space-y-2">
            <p className="text-xs text-ink-muted font-medium uppercase tracking-wide">Fases a combinar</p>
            <CollectionPicker
              all={siblings}
              selected={selectedCollections}
              onChange={setSelectedCollections}
            />
          </div>
        )}

        {selectedCollections.length === 0 && (
          <div className="card p-10 text-center">
            <Layers className="w-8 h-8 text-ink-muted opacity-40 mx-auto mb-2" />
            <p className="text-sm text-ink-secondary">
              Selecciona al menos una fase para ver estadísticas combinadas.
            </p>
          </div>
        )}

        {selectedCollections.length > 0 && (
          <>
            {/* Entity tabs: Equipos | Jugadores */}
            <div className="flex items-center gap-1 border-b border-surface-border">
              {ENTITY_TABS.map(({ id, label }) => (
                <button
                  key={id}
                  onClick={() => setEntityTab(id as EntityTab)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                    entityTab === id
                      ? 'border-brand-500 text-brand-400'
                      : 'border-transparent text-ink-muted hover:text-ink-primary'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Stat sub-tabs */}
            <div className="flex items-center gap-1 border-b border-surface-border/50">
              {STAT_TABS.map(({ id, label, Icon }) => {
                const active = entityTab === 'equipos' ? statTab === id : playerStatTab === id
                return (
                  <button
                    key={id}
                    onClick={() => entityTab === 'equipos' ? setStatTab(id as StatTab) : setPlayerStatTab(id as StatTab)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border-b-2 transition-colors -mb-px ${
                      active
                        ? 'border-brand-500/70 text-brand-400'
                        : 'border-transparent text-ink-muted hover:text-ink-primary'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </button>
                )
              })}
            </div>

            {/* Loading skeleton */}
            {isLoading && (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-9 rounded bg-surface-border/40 animate-pulse" />
                ))}
              </div>
            )}

            {/* Team stats table */}
            {!isLoading && entityTab === 'equipos' && (
              teamRows.length > 0 ? (
                <DataTable
                  columns={teamCols}
                  data={teamRows}
                  quartiles={teamQuartiles}
                  reverseColumns={reverseTeam}
                  searchable
                  searchPlaceholder="Buscar equipo…"
                  exportOptions={{ filename: 'multifase_equipos' }}
                />
              ) : (
                <p className="text-sm text-ink-secondary text-center py-8">
                  No hay datos de equipo disponibles.
                </p>
              )
            )}

            {/* Player stats table */}
            {!isLoading && entityTab === 'jugadores' && (
              playerRows.length > 0 ? (
                <DataTable
                  columns={playerStatTab === 'basic' ? PLAYER_COLS : PLAYER_ADV_COLS}
                  data={playerRows}
                  quartiles={playerQuartiles}
                  reverseColumns={playerStatTab === 'basic' ? ['turnovers_per_game'] : REVERSE_PLAYER_ADV}
                  searchable
                  searchPlaceholder="Buscar jugador…"
                  exportOptions={{ filename: `multifase_jugadores_${playerStatTab}` }}
                />
              ) : (
                <p className="text-sm text-ink-secondary text-center py-8">
                  No hay datos de jugadores disponibles.
                </p>
              )
            )}
          </>
        )}
      </div>
    </PageTransition>
  )
}
