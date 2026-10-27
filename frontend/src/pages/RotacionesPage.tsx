import { useState, useRef, useMemo, useEffect, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { useChartTheme } from '@/lib/chartTheme'
import { useCollection } from '@/context/CollectionContext'
import PageTransition from '@/components/ui/PageTransition'
import ExportButton from '@/components/ui/ExportButton'
import {
  getTeamStats, streamRotacionesAnalysis,
  type RotationPlayer, type RotationResult,
} from '@/api/client'

// ── Helpers ───────────────────────────────────────────────────────────────────

const selectCls =
  'appearance-none bg-canvas border border-line rounded-lg px-3 py-1.5 text-sm ' +
  'text-ink focus:outline-none focus:ring-2 focus:ring-focus'

function fmtPct(v: number | null | undefined) {
  if (v == null) return '—'
  return `${v.toFixed(1)}%`
}

function fmtNum(v: number | null | undefined, decimals = 2) {
  if (v == null) return '—'
  return v.toFixed(decimals)
}

/** Gini label colour CSS class */
function giniColour(label: string): string {
  if (label === 'Rotación amplia') return 'text-ok'
  if (label === 'Rotación equilibrada') return 'text-warn'
  return 'text-bad'
}

/** CV label colour CSS class */
function cvColour(label: string): string {
  if (label === 'Muy homogéneo') return 'text-ok'
  if (label === 'Moderado') return 'text-warn'
  return 'text-bad'
}

// ── Metric card ───────────────────────────────────────────────────────────────

interface MetricCardProps {
  title: string
  value: string
  subtitle?: string
  badge?: { text: string; cls: string }
  children?: React.ReactNode
}

function MetricCard({ title, value, subtitle, badge, children }: MetricCardProps) {
  return (
    <div className="card p-4 flex flex-col gap-2">
      <p className="text-xs font-medium text-ink-muted uppercase tracking-wide">{title}</p>
      <p className="text-3xl font-bold text-ink leading-none">{value}</p>
      {badge && (
        <span className={`text-xs font-semibold ${badge.cls}`}>{badge.text}</span>
      )}
      {subtitle && <p className="text-xs text-ink-faint">{subtitle}</p>}
      {children}
    </div>
  )
}

// ── Custom bar tooltip ────────────────────────────────────────────────────────

interface BarTooltipProps {
  active?: boolean
  payload?: { payload: RotationPlayer }[]
}

function BarTooltip({ active, payload }: BarTooltipProps) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="bg-canvas border border-line rounded-lg p-3 shadow-lg text-xs space-y-1">
      <p className="font-semibold text-ink text-sm">{p.player_name}</p>
      <p className="text-ink-muted">{`Min. totales: `}<span className="font-medium text-ink">{fmtNum(p.total_minutes, 1)}</span></p>
      <p className="text-ink-muted">{`Min./partido: `}<span className="font-medium text-ink">{fmtNum(p.avg_min_per_game, 1)}</span></p>
      <p className="text-ink-muted">{`% tiempo: `}<span className="font-medium text-ink">{fmtPct(p.pct_game_time)}</span></p>
      {p.starter_games > 0 && (
        <p className="text-accent-text font-medium">Titular en {p.starter_games} pj ({p.starter_pct}%)</p>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface Team { name: string; id: string }

export default function RotacionesPage() {
  const chart = useChartTheme()
  const { collection } = useCollection()

  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null)
  const [pendingTeam, setPendingTeam]   = useState<Team | null>(null)

  const [result, setResult]       = useState<RotationResult | null>(null)
  const [isFetching, setFetching] = useState(false)
  const [error, setError]         = useState<Error | null>(null)
  const [progress, setProgress]   = useState<number | null>(null)

  const exportRef = useRef<HTMLDivElement>(null)
  const streamHandle = useRef<{ cancelled: boolean }>({ cancelled: false })

  // ── Team list ──────────────────────────────────────────────────────────────

  const { data: teamData } = useQuery({
    queryKey: ['team-list-rotaciones', collection?.name],
    queryFn: () => getTeamStats(collection!.name),
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })

  const teams = useMemo(
    () =>
      (teamData?.team_stats ?? [])
        .map(t => ({ name: t.team_name, id: String(t.team_id ?? t.team_name) }))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [teamData],
  )

  useEffect(() => {
    if (teams.length > 0 && !pendingTeam) {
      const first = teams[0]
      setPendingTeam(first)
    }
  }, [teams, pendingTeam])

  // ── Analysis trigger ───────────────────────────────────────────────────────

  function handleAnalyze(e: FormEvent) {
    e.preventDefault()
    if (!pendingTeam || !collection) return
    setSelectedTeam(pendingTeam)
    triggerAnalysis(pendingTeam)
  }

  function triggerAnalysis(team: Team) {
    if (!collection) return
    const handle = { cancelled: false }
    streamHandle.current = handle
    setFetching(true)
    setError(null)
    setProgress(0)
    setResult(null)

    streamRotacionesAnalysis(
      collection.name,
      team.id,
      team.name,
      (pct) => { if (!handle.cancelled) setProgress(pct) },
    )
      .then(data => {
        if (!handle.cancelled) {
          setResult(data)
          setFetching(false)
          setProgress(null)
        }
      })
      .catch(err => {
        if (!handle.cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)))
          setFetching(false)
          setProgress(null)
        }
      })
  }

  // ── Derived data ───────────────────────────────────────────────────────────

  const chartData = useMemo(
    () => result?.players ?? [],
    [result],
  )

  const csvData = useMemo(
    () =>
      (result?.players ?? []).map(p => ({
        jugadora:          p.player_name,
        partidos:          p.games_played,
        min_totales:       fmtNum(p.total_minutes, 1),
        min_por_partido:   fmtNum(p.avg_min_per_game, 1),
        pct_tiempo:        fmtPct(p.pct_game_time),
        partidos_titular:  p.starter_games,
        pct_titular:       `${p.starter_pct}%`,
      })),
    [result],
  )

  const csvHeaders = [
    { key: 'jugadora',         label: 'Jugadora' },
    { key: 'partidos',         label: 'PJ' },
    { key: 'min_totales',      label: 'Min. totales' },
    { key: 'min_por_partido',  label: 'Min./partido' },
    { key: 'pct_tiempo',       label: '% tiempo' },
    { key: 'partidos_titular', label: 'PJ titular' },
    { key: 'pct_titular',      label: '% titular' },
  ]

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <PageTransition>
      <div className="space-y-4">

        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h1 className="text-2xl font-bold text-ink">Análisis de Rotaciones</h1>
            <p className="text-ink-muted text-sm mt-0.5">{collection?.label}</p>
          </div>
          {result && (
            <ExportButton
              filename={`rotaciones_${selectedTeam?.name ?? ''}_${collection?.name ?? ''}`}
              captureRef={exportRef}
              pdfTitle={`Rotaciones — ${selectedTeam?.name ?? ''} — ${collection?.label ?? ''}`}
              csvData={csvData}
              csvHeaders={csvHeaders}
            />
          )}
        </div>

        {/* Controls */}
        <form onSubmit={handleAnalyze} className="card p-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1">Equipo</label>
            <select
              value={pendingTeam?.id ?? ''}
              onChange={e => setPendingTeam(teams.find(t => t.id === e.target.value) ?? null)}
              className={selectCls}
            >
              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>

          <button
            type="submit"
            disabled={isFetching || !pendingTeam}
            className="bg-secondary hover:bg-secondary-hover disabled:opacity-60 text-white text-sm font-medium rounded-lg px-5 py-1.5 transition-colors"
          >
            {isFetching ? 'Analizando…' : 'Analizar'}
          </button>
        </form>

        {/* Error */}
        {error && (
          <p className="text-bad text-sm bg-bad/10 border border-bad/30 rounded-lg p-3">
            {error.message}
          </p>
        )}

        {/* Progress bar */}
        {isFetching && (
          <div className="flex flex-col gap-2 card p-4 text-ink-muted text-sm">
            <div className="flex items-center gap-3">
              <span className="inline-block w-4 h-4 border-2 border-secondary-text border-t-transparent rounded-full animate-spin flex-shrink-0" />
              Analizando partidos…
              {progress != null && (
                <span className="ml-auto text-xs text-ink-faint font-mono">{progress}%</span>
              )}
            </div>
            {progress != null && (
              <div className="h-1.5 bg-surface-raised rounded-full overflow-hidden">
                <div
                  className="h-full bg-secondary rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {!isFetching && result && (
          <div ref={exportRef} className="space-y-4">

            {/* Subtitle */}
            <p className="text-ink-muted text-xs">
              {selectedTeam?.name} · {result.total_games} partidos analizados
              {result.games_with_playbyplay < result.total_games && (
                <span className="text-warn">
                  {` · (datos play-by-play disponibles en ${result.games_with_playbyplay}/${result.total_games})`}
                </span>
              )}
            </p>

            {/* ── Row 1: % minutes cards ── */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">

              <MetricCard
                title="Quinteto más frecuente"
                value={fmtPct(result.pct_minutes_starting_five)}
                subtitle={
                  result.starting_five_names.length > 0
                    ? result.starting_five_names.join(', ')
                    : undefined
                }
                badge={
                  result.significant_player_count <= 5
                    ? { text: 'Plantilla completa', cls: 'text-warn' }
                    : undefined
                }
              >
                {result.games_with_playbyplay > 0 && (
                  <p className="text-xs text-ink-faint">
                    Iniciaron juntas{' '}
                    <span className="font-semibold text-ink">
                      {result.starting_five_games_count}/{result.games_with_playbyplay}
                    </span>{' '}
                    partidos ({result.starting_five_games_pct}%)
                  </p>
                )}
              </MetricCard>

              <MetricCard
                title="Top 5 jugadoras"
                value={fmtPct(result.pct_minutes_top5)}
                subtitle={`±${result.pct_minutes_top5_std}% entre partidos · plantilla: ${result.significant_player_count} jug.`}
                badge={
                  result.significant_player_count <= 5
                    ? { text: 'Plantilla completa', cls: 'text-warn' }
                    : undefined
                }
              />

              <MetricCard
                title="Top 8 jugadoras"
                value={fmtPct(result.pct_minutes_top8)}
                subtitle={`±${result.pct_minutes_top8_std}% entre partidos · plantilla: ${result.significant_player_count} jug.`}
                badge={
                  result.significant_player_count <= 8
                    ? { text: 'Plantilla completa', cls: 'text-warn' }
                    : undefined
                }
              />

              <div className="card p-4 flex flex-col gap-2">
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wide">
                  Cambios por partido
                </p>
                <div className="space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs text-ink-muted">Combinados (momentos)</span>
                    <div className="text-right">
                      <span className="text-xl font-bold text-ink">
                        {result.total_combined_substitutions}
                      </span>
                      <span className="text-xs text-ink-faint ml-1">
                        ({fmtNum(result.avg_combined_subs_per_game, 1)}/pj)
                      </span>
                    </div>
                  </div>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs text-ink-muted">Individuales (total)</span>
                    <div className="text-right">
                      <span className="text-xl font-bold text-ink">
                        {result.total_individual_substitutions}
                      </span>
                      <span className="text-xs text-ink-faint ml-1">
                        ({fmtNum(result.avg_individual_subs_per_game, 1)}/pj)
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stint promedio equipo */}
              <MetricCard
                title="Stint prom. equipo"
                value={result.avg_stint_min_team != null ? `${result.avg_stint_min_team} min` : '—'}
                subtitle="durac. media de cada intervalo en pista (datos PBP)"
              />
            </div>

            {/* ── Row 2: Dispersion card ── */}
            <div className="card p-4">
              <p className="text-xs font-medium text-ink-muted uppercase tracking-wide mb-3">
                Dispersión de minutos
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">

                {/* Gini */}
                <div className="space-y-1">
                  <div className="flex items-baseline gap-3">
                    <span className="text-3xl font-bold text-ink">
                      {fmtNum(result.gini_index, 3)}
                    </span>
                    <span className={`text-sm font-semibold ${giniColour(result.rotation_label)}`}>
                      {result.rotation_label}
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted">
                    Índice de Gini <span className="text-ink-faint">· media por partido, ±{fmtNum(result.gini_std, 3)} std</span>
                  </p>
                  <p className="text-xs text-ink-faint">
                    {result.rotation_label === 'Rotación amplia'
                      ? 'Los minutos están muy repartidos entre todas las jugadoras.'
                      : result.rotation_label === 'Rotación equilibrada'
                      ? 'Distribución moderada: hay algo de concentración de minutos.'
                      : 'Pocas jugadoras concentran la mayor parte del tiempo de juego.'}
                  </p>
                  {/* Gini bar */}
                  <div className="mt-2 h-2 bg-surface-raised rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        result.gini_index < 0.15 ? 'bg-ok'
                        : result.gini_index < 0.25 ? 'bg-warn'
                        : 'bg-bad'
                      }`}
                      style={{ width: `${Math.min(100, result.gini_index * 200)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-ink-faint mt-0.5">
                    <span>0 (equitativo)</span>
                    <span>0.5+</span>
                  </div>
                </div>

                {/* CV */}
                <div className="space-y-1">
                  <div className="flex items-baseline gap-3">
                    <span className="text-3xl font-bold text-ink">
                      {fmtPct(result.cv)}
                    </span>
                    <span className={`text-sm font-semibold ${cvColour(result.cv_label)}`}>
                      {result.cv_label}
                    </span>
                  </div>
                  <p className="text-xs text-ink-muted">
                    Coeficiente de variación <span className="text-ink-faint">· media por partido, ±{fmtNum(result.cv_std, 1)}% std</span>
                  </p>
                  <p className="text-xs text-ink-faint">
                    {result.cv_label === 'Muy homogéneo'
                      ? 'Las jugadoras tienen cargas de minutos muy similares entre sí.'
                      : result.cv_label === 'Moderado'
                      ? 'Hay diferencias apreciables en la carga de minutos.'
                      : 'La carga de minutos es muy desigual entre jugadoras.'}
                  </p>
                  {/* CV bar */}
                  <div className="mt-2 h-2 bg-surface-raised rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        result.cv < 20 ? 'bg-ok'
                        : result.cv < 40 ? 'bg-warn'
                        : 'bg-bad'
                      }`}
                      style={{ width: `${Math.min(100, result.cv / 2)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-ink-faint mt-0.5">
                    <span>0%</span>
                    <span>200%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Bar chart ── */}
            {chartData.length > 0 && (
              <div className="card p-4">
                <p className="text-xs font-medium text-ink-muted uppercase tracking-wide mb-3">
                  Distribución de minutos por jugadora
                </p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={chartData}
                    margin={{ top: 4, right: 8, left: 0, bottom: 60 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} strokeOpacity={0.6} />
                    <XAxis
                      dataKey="player_name"
                      tick={{ fontSize: 10, fill: chart.axis }}
                      angle={-40}
                      textAnchor="end"
                      interval={0}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: chart.axis }}
                      label={{
                        value: 'Min. totales',
                        angle: -90,
                        position: 'insideLeft',
                        offset: 10,
                        style: { fontSize: 10, fill: chart.axis },
                      }}
                    />
                    <Tooltip content={<BarTooltip />} />
                    <Bar dataKey="total_minutes" radius={[3, 3, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.is_starter ? chart.series[0] : chart.reference}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex items-center gap-4 mt-1 text-xs text-ink-faint justify-end">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-3 h-3 rounded-sm bg-chart-1" />
                    Titular
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-3 h-3 rounded-sm bg-ink-faint" />
                    Suplente
                  </span>
                </div>
              </div>
            )}

            {/* ── Detail table ── */}
            {result.players.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-line shadow-sm">
                <table className="w-full text-sm">
                  <thead className="bg-canvas text-ink">
                    <tr>
                      <th className="px-3 py-2 text-left font-semibold">Jugadora</th>
                      <th className="px-3 py-2 text-center font-semibold w-12">PJ</th>
                      <th className="px-3 py-2 text-center font-semibold w-24">Min. totales</th>
                      <th className="px-3 py-2 text-center font-semibold w-24">Min./partido</th>
                      <th className="px-3 py-2 text-center font-semibold w-20">% tiempo</th>
                      <th className="px-3 py-2 text-center font-semibold w-24">Stint prom.</th>
                      <th className="px-3 py-2 text-center font-semibold w-28">PJ titular</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {result.players.map((p, i) => {
                      const pctCls =
                        p.pct_game_time >= 75 ? 'text-ok font-semibold'
                        : p.pct_game_time >= 40 ? 'text-ink'
                        : 'text-ink-faint'
                      const rowCls = i % 2 === 0
                        ? 'bg-canvas hover:bg-surface-raised'
                        : 'bg-surface-raised hover:bg-surface-raised'
                      return (
                        <tr key={p.player_id} className={`transition-colors ${rowCls}`}>
                          <td className="px-3 py-2 font-medium text-ink">
                            <span className="flex items-center gap-2">
                              {p.player_name}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center text-ink-muted">{p.games_played}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">{fmtNum(p.total_minutes, 1)}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">{fmtNum(p.avg_min_per_game, 1)}</td>
                          <td className={`px-3 py-2 text-center ${pctCls}`}>{fmtPct(p.pct_game_time)}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">
                            {p.avg_stint_min != null
                              ? <span title={`${p.total_pbp_stints} stints · media min/stint sobre datos PBP`}>{fmtNum(p.avg_stint_min, 1)} min</span>
                              : <span className="text-ink-faint text-xs">—</span>
                            }
                          </td>
                          <td className="px-3 py-2 text-center">
                            {p.starter_games > 0 ? (
                              <span title={`Titular en ${p.starter_pct}% de los partidos`}>
                                <span className="font-semibold text-ink">{p.starter_games}</span>
                                <span className="text-xs text-ink-faint ml-1">({p.starter_pct}%)</span>
                              </span>
                            ) : (
                              <span className="text-ink-faint text-xs">—</span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── Otras jugadoras (marginal / filial) ── */}
            {result.marginal_players.length > 0 && (
              <details className="rounded-xl border border-line overflow-hidden group">
                <summary className="flex items-center justify-between px-4 py-2.5 bg-surface-raised hover:bg-surface-raised cursor-pointer text-sm font-medium text-ink-muted select-none list-none">
                  <span>
                    Otras jugadoras
                    <span className="ml-2 text-xs font-normal text-ink-faint">
                      ({result.marginal_players.length}) — menos del 15% de partidos y media &lt; 5 min — excluidas del análisis
                    </span>
                  </span>
                  <svg className="w-4 h-4 transition-transform group-open:rotate-180" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 10.94L2.06 5l1.41-1.41L8 8.12l4.53-4.53L13.94 5z"/>
                  </svg>
                </summary>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-surface-raised text-ink-muted">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">Jugadora</th>
                        <th className="px-3 py-2 text-center font-medium w-12">PJ</th>
                        <th className="px-3 py-2 text-center font-medium w-24">Min. totales</th>
                        <th className="px-3 py-2 text-center font-medium w-24">Min./partido</th>
                        <th className="px-3 py-2 text-center font-medium w-20">% tiempo</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line opacity-70">
                      {result.marginal_players.map(p => (
                        <tr key={p.player_id} className="bg-canvas hover:bg-surface-raised transition-colors">
                          <td className="px-3 py-2 text-ink-muted">{p.player_name}</td>
                          <td className="px-3 py-2 text-center text-ink-faint">{p.games_played}</td>
                          <td className="px-3 py-2 text-center text-ink-faint">{fmtNum(p.total_minutes, 1)}</td>
                          <td className="px-3 py-2 text-center text-ink-faint">{fmtNum(p.avg_min_per_game, 1)}</td>
                          <td className="px-3 py-2 text-center text-ink-faint">{fmtPct(p.pct_game_time)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

          </div>
        )}

      </div>
    </PageTransition>
  )
}
