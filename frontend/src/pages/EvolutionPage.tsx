/**
 * EvolutionPage — Fase 3
 * Evolución temporal de métricas con Recharts multi-equipo/multi-stat + rolling average + brush zoom.
 */
import { useState, useMemo, useRef } from 'react'
import { useQuery, useQueries } from '@tanstack/react-query'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Brush,
} from 'recharts'
import { TrendingUp, X, ChevronDown } from 'lucide-react'

import { useCollection } from '@/context/CollectionContext'
import { getTeamEvolution, getCompetitionEvolution, type EvolutionPoint, type CompetitionEvolutionPoint, type TeamEntry } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'
import ExportButton from '@/components/ui/ExportButton'

// -- Helpers ------------------------------------------------------------------

// Softer palette for up to 8 simultaneous team lines
const TEAM_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
  '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
]

// Stat options grouped by category
const STAT_GROUPS = [
  {
    label: 'Generales',
    options: [
      { key: 'points',         label: 'Puntos' },
      { key: 'points_allowed', label: 'Puntos recibidos' },
      { key: 'rebounds',       label: 'Rebotes totales' },
      { key: 'def_rebounds',   label: 'Rebotes defensivos' },
      { key: 'off_rebounds',   label: 'Rebotes ofensivos' },
      { key: 'assists',        label: 'Asistencias' },
      { key: 'steals',         label: 'Robos' },
      { key: 'turnovers',      label: 'Pérdidas' },
      { key: 'blocks',         label: 'Tapones' },
    ],
  },
  {
    label: 'Tiro',
    options: [
      { key: 'fg2_made',       label: 'T2 anotados' },
      { key: 'fg2_attempts',   label: 'T2 intentados' },
      { key: 'fg3_made',       label: 'T3 anotados' },
      { key: 'fg3_attempts',   label: 'T3 intentados' },
      { key: 'ft_made',        label: 'TL anotados' },
      { key: 'ft_attempts',    label: 'TL intentados' },
      { key: 'fg2_percentage', label: '% Tiros de 2' },
      { key: 'fg3_percentage', label: '% Tiros de 3' },
      { key: 'ft_percentage',  label: '% Tiros libres' },
    ],
  },
  {
    label: 'Avanzadas',
    options: [
      { key: 'possessions',       label: 'Posesiones' },
      { key: 'offensive_rating',  label: 'Rating Ofensivo' },
      { key: 'defensive_rating',  label: 'Rating Defensivo' },
      { key: 'net_rating',        label: 'Net Rating' },
      { key: 'efg_percentage',    label: 'eFG%' },
      { key: 'true_shooting',     label: 'TS%' },
      { key: 'three_point_rate',  label: '3Pr (Tasa triples)' },
      { key: 'free_throw_rate',   label: 'FTr (Tasa TL)' },
      { key: 'assist_fg_rate',    label: 'AST/FG%' },
      { key: 'assist_rate',       label: 'AST%' },
      { key: 'turnover_rate',     label: 'TOV%' },
      { key: 'steal_rate',        label: 'ROB%' },
      { key: 'block_rate',        label: 'TAP%' },
      { key: 'off_rebound_rate',  label: 'ORB%' },
      { key: 'def_rebound_rate',  label: 'RD%' },
    ],
  },
] as const

const STAT_LABEL_MAP: Record<string, string> = Object.fromEntries(
  STAT_GROUPS.flatMap(g => g.options.map(o => [o.key, o.label]))
)

const WINDOW_OPTIONS = [3, 5, 10]

// Merge game-by-game points from multiple teams into a single array keyed by game_number
function mergeSeriesData(
  teamSeries: { team: string; data: EvolutionPoint[] }[],
  competitionData?: CompetitionEvolutionPoint[],
): Array<Record<string, unknown>> {
  const maxGames = Math.max(
    0,
    ...teamSeries.map(s => s.data.length),
    competitionData?.length ?? 0,
  )
  return Array.from({ length: maxGames }, (_, i) => {
    const row: Record<string, unknown> = { game: i + 1 }
    teamSeries.forEach(({ team, data }) => {
      const pt = data[i]
      if (pt) {
        row[`${team}_raw`] = pt.value
        row[`${team}_avg`] = pt.rolling_avg
        row[`${team}_cum`] = pt.cumulative_avg
        row[`${team}_won`] = pt.won
        row[`${team}_opp`] = pt.opponent
        row[`${team}_date`] = pt.game_date
      }
    })
    if (competitionData?.[i]) {
      row['comp_rolling']    = competitionData[i].competition_rolling
      row['comp_cumulative'] = competitionData[i].competition_cumulative
    }
    return row
  })
}

// -- Component ----------------------------------------------------------------

export default function EvolutionPage() {
  const { collection } = useCollection()

  const [selectedTeams, setSelectedTeams] = useState<string[]>([])
  const [stat, setStat] = useState<string>('points')
  const [rollingWindow, setRollingWindow] = useState(5)
  const [showRolling, setShowRolling] = useState(true)
  const [showRaw, setShowRaw] = useState(true)
  const [showCumulative, setShowCumulative] = useState(false)
  const [showCompetitionRolling, setShowCompetitionRolling] = useState(false)
  const [showCompetitionCumulative, setShowCompetitionCumulative] = useState(false)

  // Fetch team list
  const { data: teamList = [] } = useQuery({
    queryKey: ['team-list', collection?.name],
    queryFn: () => fetch(`/api/v1/teams/${encodeURIComponent(collection!.name)}/teams`)
      .then(r => r.json()) as Promise<TeamEntry[]>,
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })

  // Helper: resolve display name from ID
  const teamName = (id: string) => teamList.find(t => t.id === id)?.name ?? id

  // Fetch evolution data for each selected team in parallel
  const evolutionQueries = useQueries({
    queries: selectedTeams.map(team => ({
      queryKey: ['evolution', collection?.name, team, stat, rollingWindow],
      queryFn: () => getTeamEvolution(collection!.name, team, stat, rollingWindow),
      enabled: Boolean(collection),
      staleTime: 5 * 60_000,
    })),
  })

  // Fetch competition-wide averages only when needed
  const competitionQuery = useQuery({
    queryKey: ['competition-evolution', collection?.name, stat, rollingWindow],
    queryFn: () => getCompetitionEvolution(collection!.name, stat, rollingWindow),
    enabled: Boolean(collection) && (showCompetitionRolling || showCompetitionCumulative),
    staleTime: 5 * 60_000,
  })

  const isLoading = evolutionQueries.some(q => q.isLoading)

  // Build merged chart data
  const chartData = useMemo(() => {
    const teamSeries = selectedTeams.map((team, idx) => ({
      team,
      data: evolutionQueries[idx]?.data ?? [],
    }))
    return mergeSeriesData(teamSeries, competitionQuery.data)
  }, [selectedTeams, evolutionQueries, competitionQuery.data])

  const statLabel = STAT_LABEL_MAP[stat] ?? stat

  const chartRef = useRef<HTMLDivElement>(null)

  const csvHeaders = useMemo(() => {
    const cols: { key: string; label: string }[] = [{ key: 'game', label: 'Jornada' }]
    selectedTeams.forEach(team => {
      if (showRaw)        cols.push({ key: `${team}_raw`, label: `${teamName(team)} (partido)` })
      if (showRolling)    cols.push({ key: `${team}_avg`, label: `${teamName(team)} (media ${rollingWindow}J)` })
      if (showCumulative) cols.push({ key: `${team}_cum`, label: `${teamName(team)} (acumulado)` })
    })
    if (showCompetitionRolling)    cols.push({ key: 'comp_rolling',    label: `Liga (media ${rollingWindow}J)` })
    if (showCompetitionCumulative) cols.push({ key: 'comp_cumulative', label: 'Liga (acumulado)' })
    return cols
  }, [selectedTeams, showRaw, showRolling, showCumulative, showCompetitionRolling, showCompetitionCumulative, rollingWindow])

  function toggleTeam(team: string) {
    setSelectedTeams(prev =>
      prev.includes(team) ? prev.filter(t => t !== team) : [...prev.slice(0, 7), team]
    )
  }

  return (
    <PageTransition>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink-primary">Evolución Temporal</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
          </div>
          <ExportButton
            filename={`evolucion_${stat}_${collection?.name ?? ''}`}
            captureRef={chartRef}
            pdfTitle={`Evolución Temporal — ${statLabel} — ${collection?.label ?? ''}`}
            csvData={chartData}
            csvHeaders={csvHeaders}
          />
        </div>

        {/* Controls */}
        <div className="card p-4 flex flex-wrap gap-3 items-center">
          {/* Stat selector with optgroups */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-secondary font-medium uppercase tracking-wide">Métrica</span>
            <div className="relative">
              <select
                value={stat}
                onChange={e => setStat(e.target.value)}
                className="appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
              >
                {STAT_GROUPS.map(group => (
                  <optgroup key={group.label} label={group.label}>
                    {group.options.map(o => (
                      <option key={o.key} value={o.key}>{o.label}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-secondary" />
            </div>
          </div>

          {/* Rolling window */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-secondary font-medium uppercase tracking-wide">Media móvil</span>
            <div className="flex gap-1">
              {WINDOW_OPTIONS.map(w => (
                <button
                  key={w}
                  onClick={() => setRollingWindow(w)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                    rollingWindow === w
                      ? 'bg-accent-500 text-white'
                      : 'bg-surface-base border border-surface-border text-ink-secondary hover:bg-surface-hover'
                  }`}
                >
                  {w}J
                </button>
              ))}
            </div>
          </div>

          {/* Series toggles */}
          <div className="flex items-center gap-3 ml-auto flex-wrap">
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showRaw}    onChange={e => setShowRaw(e.target.checked)}    className="rounded" /> Por partido
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showRolling} onChange={e => setShowRolling(e.target.checked)} className="rounded" /> Media móvil
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showCumulative} onChange={e => setShowCumulative(e.target.checked)} className="rounded" /> Promedio acumulado
            </label>
            <span className="text-ink-muted text-xs select-none">|</span>
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showCompetitionRolling} onChange={e => setShowCompetitionRolling(e.target.checked)} className="rounded" />
              <span>Liga media móvil{competitionQuery.isFetching ? ' …' : ''}</span>
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showCompetitionCumulative} onChange={e => setShowCompetitionCumulative(e.target.checked)} className="rounded" />
              <span>Liga acumulado{competitionQuery.isFetching ? ' …' : ''}</span>
            </label>
          </div>
        </div>

        {/* Team chips */}
        <div className="card p-3">
          <p className="text-xs text-ink-secondary font-medium uppercase tracking-wide mb-2">
            Equipos seleccionados ({selectedTeams.length}/8)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {selectedTeams.map((team, idx) => (
              <span
                key={team}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium text-white"
                style={{ backgroundColor: TEAM_COLORS[idx % TEAM_COLORS.length] }}
              >
                {teamName(team)}
                <button onClick={() => toggleTeam(team)} className="hover:opacity-70">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            {selectedTeams.length === 0 && (
              <span className="text-xs text-ink-secondary italic">
                Selecciona equipos de la lista inferior
              </span>
            )}
          </div>
          {/* Team list */}
          {teamList.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2 border-t border-surface-border pt-2">
              {teamList.filter(t => !selectedTeams.includes(t.id)).map(team => (
                <button
                  key={team.id}
                  onClick={() => toggleTeam(team.id)}
                  className="px-2 py-0.5 rounded text-xs border border-surface-border text-ink-secondary hover:border-accent-400 hover:text-accent-400 transition-colors"
                >
                  + {team.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Chart */}
        <div className="card p-4" ref={chartRef}>
          {selectedTeams.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 gap-2 text-center">
              <TrendingUp className="w-10 h-10 text-accent-400 opacity-40" />
              <p className="text-ink-secondary text-sm">Selecciona al menos un equipo para ver la evolución</p>
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center h-64">
              <div className="w-8 h-8 border-2 border-accent-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-ink-secondary mb-3">
                {statLabel} por partido — {collection?.label}
              </p>
              <ResponsiveContainer width="100%" height={340}>
                <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis
                    dataKey="game"
                    tick={{ fontSize: 11, fill: '#6b7280' }}
                    label={{ value: 'Jornada', position: 'insideBottomRight', offset: -5, fontSize: 11, fill: '#6b7280' }}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} width={36} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #333', borderRadius: 8, fontSize: 12 }}
                    labelFormatter={v => `Jornada ${v}`}
                    formatter={(value: number, name: string) => {
                      if (name === 'comp_rolling')    return [typeof value === 'number' ? value.toFixed(1) : value, `Liga media ${rollingWindow}J`]
                      if (name === 'comp_cumulative') return [typeof value === 'number' ? value.toFixed(1) : value, 'Liga acumulado']
                      if (name.endsWith('_avg'))      return [typeof value === 'number' ? value.toFixed(1) : value, `Media ${rollingWindow}J`]
                      if (name.endsWith('_cum'))      return [typeof value === 'number' ? value.toFixed(1) : value, 'Acumulado']
                      return [typeof value === 'number' ? value.toFixed(1) : value, 'Por partido']
                    }}
                  />
                  <Legend
                    formatter={name => {
                      if (name === 'comp_rolling')    return `Liga (media ${rollingWindow}J)`
                      if (name === 'comp_cumulative') return 'Liga (acumulado)'
                      const team = name.replace(/_raw$|_avg$|_cum$/, '')
                      if (name.endsWith('_avg')) return `${team} (media ${rollingWindow}J)`
                      if (name.endsWith('_cum')) return `${team} (acumulado)`
                      return team
                    }}
                    wrapperStyle={{ fontSize: 11 }}
                  />
                  <Brush dataKey="game" height={20} stroke="#444" fill="#1a1a2e" travellerWidth={6} />
                  {selectedTeams.map((team, idx) => {
                    const color = TEAM_COLORS[idx % TEAM_COLORS.length]
                    return (
                      <>
                        {showRaw && (
                          <Line
                            key={`${team}_raw`}
                            type="monotone"
                            dataKey={`${team}_raw`}
                            stroke={color}
                            strokeWidth={1.5}
                            strokeOpacity={0.45}
                            dot={false}
                            connectNulls
                            name={`${team}_raw`}
                          />
                        )}
                        {showRolling && (
                          <Line
                            key={`${team}_avg`}
                            type="monotone"
                            dataKey={`${team}_avg`}
                            stroke={color}
                            strokeWidth={2.5}
                            dot={false}
                            connectNulls
                            name={`${team}_avg`}
                          />
                        )}
                        {showCumulative && (
                          <Line
                            key={`${team}_cum`}
                            type="monotone"
                            dataKey={`${team}_cum`}
                            stroke={color}
                            strokeWidth={2}
                            strokeDasharray="5 3"
                            dot={false}
                            connectNulls
                            name={`${team}_cum`}
                          />
                        )}
                      </>
                    )
                  })}
                  {/* Competition-wide lines (shared across all teams) */}
                  {showCompetitionRolling && (
                    <Line
                      key="comp_rolling"
                      type="monotone"
                      dataKey="comp_rolling"
                      stroke="#9ca3af"
                      strokeWidth={2}
                      dot={false}
                      connectNulls
                      name="comp_rolling"
                    />
                  )}
                  {showCompetitionCumulative && (
                    <Line
                      key="comp_cumulative"
                      type="monotone"
                      dataKey="comp_cumulative"
                      stroke="#6b7280"
                      strokeWidth={2}
                      strokeDasharray="6 3"
                      dot={false}
                      connectNulls
                      name="comp_cumulative"
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </PageTransition>
  )
}
