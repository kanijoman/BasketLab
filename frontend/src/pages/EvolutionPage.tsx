/**
 * EvolutionPage — Fase 3
 * Evolución temporal de métricas con Recharts multi-equipo/multi-stat + rolling average + brush zoom.
 */
import { useState, useMemo } from 'react'
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
import { getTeamEvolution, type EvolutionPoint } from '@/api/client'
import PageTransition from '@/components/ui/PageTransition'

// -- Helpers ------------------------------------------------------------------

// Softer palette for up to 8 simultaneous team lines
const TEAM_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
  '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
]

const STAT_OPTIONS = [
  { key: 'points',    label: 'Puntos'       },
  { key: 'assists',   label: 'Asistencias'  },
  { key: 'rebounds',  label: 'Rebotes'      },
  { key: 'steals',    label: 'Robos'        },
  { key: 'turnovers', label: 'Pérdidas'     },
  { key: 'blocks',    label: 'Tapones'      },
] as const

const WINDOW_OPTIONS = [3, 5, 10]

// Merge game-by-game points from multiple teams into a single array keyed by game_number
function mergeSeriesData(
  teamSeries: { team: string; data: EvolutionPoint[] }[],
): Array<Record<string, unknown>> {
  const maxGames = Math.max(0, ...teamSeries.map(s => s.data.length))
  return Array.from({ length: maxGames }, (_, i) => {
    const row: Record<string, unknown> = { game: i + 1 }
    teamSeries.forEach(({ team, data }) => {
      const pt = data[i]
      if (pt) {
        row[`${team}_raw`] = pt.value
        row[`${team}_avg`] = pt.rolling_avg
        row[`${team}_won`] = pt.won
        row[`${team}_opp`] = pt.opponent
        row[`${team}_date`] = pt.game_date
      }
    })
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

  // Fetch team list
  const { data: teamList = [] } = useQuery({
    queryKey: ['team-list', collection?.name],
    queryFn: () => fetch(`/api/v1/teams/${encodeURIComponent(collection!.name)}/teams`)
      .then(r => r.json()) as Promise<string[]>,
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })

  // Fetch evolution data for each selected team in parallel
  const evolutionQueries = useQueries({
    queries: selectedTeams.map(team => ({
      queryKey: ['evolution', collection?.name, team, stat, rollingWindow],
      queryFn: () => getTeamEvolution(collection!.name, team, stat, rollingWindow),
      enabled: Boolean(collection),
      staleTime: 5 * 60_000,
    })),
  })

  const isLoading = evolutionQueries.some(q => q.isLoading)

  // Build merged chart data
  const chartData = useMemo(() => {
    const teamSeries = selectedTeams.map((team, idx) => ({
      team,
      data: evolutionQueries[idx]?.data ?? [],
    }))
    return mergeSeriesData(teamSeries)
  }, [selectedTeams, evolutionQueries])

  const statLabel = STAT_OPTIONS.find(o => o.key === stat)?.label ?? stat

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
        </div>

        {/* Controls */}
        <div className="card p-4 flex flex-wrap gap-3 items-center">
          {/* Stat selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-ink-secondary font-medium uppercase tracking-wide">Métrica</span>
            <div className="relative">
              <select
                value={stat}
                onChange={e => setStat(e.target.value)}
                className="appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 pr-8 text-sm text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400"
              >
                {STAT_OPTIONS.map(o => (
                  <option key={o.key} value={o.key}>{o.label}</option>
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

          {/* Toggle raw/rolling */}
          <div className="flex items-center gap-3 ml-auto">
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showRaw}    onChange={e => setShowRaw(e.target.checked)}    className="rounded" /> Por partido
            </label>
            <label className="flex items-center gap-1.5 cursor-pointer text-xs text-ink-secondary">
              <input type="checkbox" checked={showRolling} onChange={e => setShowRolling(e.target.checked)} className="rounded" /> Media móvil
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
                {team}
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
              {teamList.filter(t => !selectedTeams.includes(t)).map(team => (
                <button
                  key={team}
                  onClick={() => toggleTeam(team)}
                  className="px-2 py-0.5 rounded text-xs border border-surface-border text-ink-secondary hover:border-accent-400 hover:text-accent-400 transition-colors"
                >
                  + {team}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Chart */}
        <div className="card p-4">
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
                      const isRolling = name.endsWith('_avg')
                      const label = isRolling ? `Media ${rollingWindow}J` : 'Por partido'
                      return [typeof value === 'number' ? value.toFixed(1) : value, label]
                    }}
                  />
                  <Legend
                    formatter={name => {
                      const team = name.replace(/_raw$|_avg$/, '')
                      const isRolling = name.endsWith('_avg')
                      return `${team}${isRolling ? ` (media ${rollingWindow}J)` : ''}`
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
                      </>
                    )
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </PageTransition>
  )
}
