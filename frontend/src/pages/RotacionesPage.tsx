import { useState, useRef, useMemo, useEffect, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { useCollection } from '@/context/CollectionContext'
import PageTransition from '@/components/ui/PageTransition'
import ExportButton from '@/components/ui/ExportButton'
import {
  getTeamStats, streamRotacionesAnalysis,
  type RotationPlayer, type RotationResult,
} from '@/api/client'

// ── Helpers ───────────────────────────────────────────────────────────────────

const selectCls =
  'appearance-none bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 text-sm ' +
  'text-ink-primary focus:outline-none focus:ring-2 focus:ring-accent-400'

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
  if (label === 'Rotación amplia') return 'text-green-600 dark:text-green-400'
  if (label === 'Rotación equilibrada') return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
}

/** CV label colour CSS class */
function cvColour(label: string): string {
  if (label === 'Muy homogéneo') return 'text-green-600 dark:text-green-400'
  if (label === 'Moderado') return 'text-yellow-600 dark:text-yellow-400'
  return 'text-red-600 dark:text-red-400'
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
      <p className="text-xs font-medium text-ink-secondary uppercase tracking-wide">{title}</p>
      <p className="text-3xl font-bold text-ink-primary leading-none">{value}</p>
      {badge && (
        <span className={`text-xs font-semibold ${badge.cls}`}>{badge.text}</span>
      )}
      {subtitle && <p className="text-xs text-ink-muted">{subtitle}</p>}
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
    <div className="bg-surface-base border border-surface-border rounded-lg p-3 shadow-lg text-xs space-y-1">
      <p className="font-semibold text-ink-primary text-sm">{p.player_name}</p>
      <p className="text-ink-secondary">{`Min. totales: `}<span className="font-medium text-ink-primary">{fmtNum(p.total_minutes, 1)}</span></p>
      <p className="text-ink-secondary">{`Min./partido: `}<span className="font-medium text-ink-primary">{fmtNum(p.avg_min_per_game, 1)}</span></p>
      <p className="text-ink-secondary">{`% tiempo: `}<span className="font-medium text-ink-primary">{fmtPct(p.pct_game_time)}</span></p>
      {p.starter_games > 0 && (
        <p className="text-brand-500 font-medium">Titular en {p.starter_games} pj ({p.starter_pct}%)</p>
      )}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

interface Team { name: string; id: string }

export default function RotacionesPage() {
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
            <h1 className="text-2xl font-bold text-ink-primary">Análisis de Rotaciones</h1>
            <p className="text-ink-secondary text-sm mt-0.5">{collection?.label}</p>
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
            <label className="block text-xs font-medium text-ink-secondary mb-1">Equipo</label>
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
            className="bg-accent-600 hover:bg-accent-700 disabled:opacity-60 text-white text-sm font-medium rounded-lg px-5 py-1.5 transition-colors"
          >
            {isFetching ? 'Analizando…' : 'Analizar'}
          </button>
        </form>

        {/* Error */}
        {error && (
          <p className="text-red-600 text-sm bg-red-50 dark:bg-red-900/20 border border-red-200 rounded-lg p-3">
            {error.message}
          </p>
        )}

        {/* Progress bar */}
        {isFetching && (
          <div className="flex flex-col gap-2 card p-4 text-ink-secondary text-sm">
            <div className="flex items-center gap-3">
              <span className="inline-block w-4 h-4 border-2 border-accent-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              Analizando partidos…
              {progress != null && (
                <span className="ml-auto text-xs text-ink-muted font-mono">{progress}%</span>
              )}
            </div>
            {progress != null && (
              <div className="h-1.5 bg-surface-hover rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent-500 rounded-full transition-all duration-300"
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
            <p className="text-ink-secondary text-xs">
              {selectedTeam?.name} · {result.total_games} partidos analizados
              {result.games_with_playbyplay < result.total_games && (
                <span className="text-amber-600 dark:text-amber-400">
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
                    ? { text: 'Plantilla completa', cls: 'text-amber-600 dark:text-amber-400' }
                    : undefined
                }
              >
                {result.games_with_playbyplay > 0 && (
                  <p className="text-xs text-ink-muted">
                    Iniciaron juntas{' '}
                    <span className="font-semibold text-ink-primary">
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
                    ? { text: 'Plantilla completa', cls: 'text-amber-600 dark:text-amber-400' }
                    : undefined
                }
              />

              <MetricCard
                title="Top 8 jugadoras"
                value={fmtPct(result.pct_minutes_top8)}
                subtitle={`±${result.pct_minutes_top8_std}% entre partidos · plantilla: ${result.significant_player_count} jug.`}
                badge={
                  result.significant_player_count <= 8
                    ? { text: 'Plantilla completa', cls: 'text-amber-600 dark:text-amber-400' }
                    : undefined
                }
              />

              <div className="card p-4 flex flex-col gap-2">
                <p className="text-xs font-medium text-ink-secondary uppercase tracking-wide">
                  Cambios por partido
                </p>
                <div className="space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs text-ink-secondary">Combinados (momentos)</span>
                    <div className="text-right">
                      <span className="text-xl font-bold text-ink-primary">
                        {result.total_combined_substitutions}
                      </span>
                      <span className="text-xs text-ink-muted ml-1">
                        ({fmtNum(result.avg_combined_subs_per_game, 1)}/pj)
                      </span>
                    </div>
                  </div>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs text-ink-secondary">Individuales (total)</span>
                    <div className="text-right">
                      <span className="text-xl font-bold text-ink-primary">
                        {result.total_individual_substitutions}
                      </span>
                      <span className="text-xs text-ink-muted ml-1">
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
              <p className="text-xs font-medium text-ink-secondary uppercase tracking-wide mb-3">
                Dispersión de minutos
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">

                {/* Gini */}
                <div className="space-y-1">
                  <div className="flex items-baseline gap-3">
                    <span className="text-3xl font-bold text-ink-primary">
                      {fmtNum(result.gini_index, 3)}
                    </span>
                    <span className={`text-sm font-semibold ${giniColour(result.rotation_label)}`}>
                      {result.rotation_label}
                    </span>
                  </div>
                  <p className="text-xs text-ink-secondary">
                    Índice de Gini <span className="text-ink-muted">· media por partido, ±{fmtNum(result.gini_std, 3)} std</span>
                  </p>
                  <p className="text-xs text-ink-muted">
                    {result.rotation_label === 'Rotación amplia'
                      ? 'Los minutos están muy repartidos entre todas las jugadoras.'
                      : result.rotation_label === 'Rotación equilibrada'
                      ? 'Distribución moderada: hay algo de concentración de minutos.'
                      : 'Pocas jugadoras concentran la mayor parte del tiempo de juego.'}
                  </p>
                  {/* Gini bar */}
                  <div className="mt-2 h-2 bg-surface-hover rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        result.gini_index < 0.15 ? 'bg-green-500'
                        : result.gini_index < 0.25 ? 'bg-yellow-500'
                        : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(100, result.gini_index * 200)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-ink-muted mt-0.5">
                    <span>0 (equitativo)</span>
                    <span>0.5+</span>
                  </div>
                </div>

                {/* CV */}
                <div className="space-y-1">
                  <div className="flex items-baseline gap-3">
                    <span className="text-3xl font-bold text-ink-primary">
                      {fmtPct(result.cv)}
                    </span>
                    <span className={`text-sm font-semibold ${cvColour(result.cv_label)}`}>
                      {result.cv_label}
                    </span>
                  </div>
                  <p className="text-xs text-ink-secondary">
                    Coeficiente de variación <span className="text-ink-muted">· media por partido, ±{fmtNum(result.cv_std, 1)}% std</span>
                  </p>
                  <p className="text-xs text-ink-muted">
                    {result.cv_label === 'Muy homogéneo'
                      ? 'Las jugadoras tienen cargas de minutos muy similares entre sí.'
                      : result.cv_label === 'Moderado'
                      ? 'Hay diferencias apreciables en la carga de minutos.'
                      : 'La carga de minutos es muy desigual entre jugadoras.'}
                  </p>
                  {/* CV bar */}
                  <div className="mt-2 h-2 bg-surface-hover rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        result.cv < 20 ? 'bg-green-500'
                        : result.cv < 40 ? 'bg-yellow-500'
                        : 'bg-red-500'
                      }`}
                      style={{ width: `${Math.min(100, result.cv / 2)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-ink-muted mt-0.5">
                    <span>0%</span>
                    <span>200%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Bar chart ── */}
            {chartData.length > 0 && (
              <div className="card p-4">
                <p className="text-xs font-medium text-ink-secondary uppercase tracking-wide mb-3">
                  Distribución de minutos por jugadora
                </p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={chartData}
                    margin={{ top: 4, right: 8, left: 0, bottom: 60 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-surface-border, #334155)" />
                    <XAxis
                      dataKey="player_name"
                      tick={{ fontSize: 10, fill: 'var(--color-ink-secondary, #94a3b8)' }}
                      angle={-40}
                      textAnchor="end"
                      interval={0}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: 'var(--color-ink-secondary, #94a3b8)' }}
                      label={{
                        value: 'Min. totales',
                        angle: -90,
                        position: 'insideLeft',
                        offset: 10,
                        style: { fontSize: 10, fill: 'var(--color-ink-secondary, #94a3b8)' },
                      }}
                    />
                    <Tooltip content={<BarTooltip />} />
                    <Bar dataKey="total_minutes" radius={[3, 3, 0, 0]}>
                      {chartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.is_starter
                            ? 'var(--color-brand-500, #3b82f6)'
                            : 'var(--color-surface-400, #64748b)'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="flex items-center gap-4 mt-1 text-xs text-ink-muted justify-end">
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-3 h-3 rounded-sm bg-brand-500" />
                    Titular
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block w-3 h-3 rounded-sm bg-surface-400" />
                    Suplente
                  </span>
                </div>
              </div>
            )}

            {/* ── Detail table ── */}
            {result.players.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-surface-border shadow-sm">
                <table className="w-full text-sm">
                  <thead className="bg-court-950 text-white">
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
                  <tbody className="divide-y divide-surface-border">
                    {result.players.map((p, i) => {
                      const pctCls =
                        p.pct_game_time >= 75 ? 'text-green-700 dark:text-green-400 font-semibold'
                        : p.pct_game_time >= 40 ? 'text-ink-primary'
                        : 'text-ink-muted'
                      const rowCls = i % 2 === 0
                        ? 'bg-surface-base hover:bg-surface-hover'
                        : 'bg-surface-muted hover:bg-surface-hover'
                      return (
                        <tr key={p.player_id} className={`transition-colors ${rowCls}`}>
                          <td className="px-3 py-2 font-medium text-ink-primary">
                            <span className="flex items-center gap-2">
                              {p.player_name}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center text-ink-secondary">{p.games_played}</td>
                          <td className="px-3 py-2 text-center text-ink-secondary">{fmtNum(p.total_minutes, 1)}</td>
                          <td className="px-3 py-2 text-center text-ink-secondary">{fmtNum(p.avg_min_per_game, 1)}</td>
                          <td className={`px-3 py-2 text-center ${pctCls}`}>{fmtPct(p.pct_game_time)}</td>
                          <td className="px-3 py-2 text-center text-ink-secondary">
                            {p.avg_stint_min != null
                              ? <span title={`${p.total_pbp_stints} stints · media min/stint sobre datos PBP`}>{fmtNum(p.avg_stint_min, 1)} min</span>
                              : <span className="text-ink-muted text-xs">—</span>
                            }
                          </td>
                          <td className="px-3 py-2 text-center">
                            {p.starter_games > 0 ? (
                              <span title={`Titular en ${p.starter_pct}% de los partidos`}>
                                <span className="font-semibold text-ink-primary">{p.starter_games}</span>
                                <span className="text-xs text-ink-muted ml-1">({p.starter_pct}%)</span>
                              </span>
                            ) : (
                              <span className="text-ink-muted text-xs">—</span>
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
              <details className="rounded-xl border border-surface-border overflow-hidden group">
                <summary className="flex items-center justify-between px-4 py-2.5 bg-surface-muted hover:bg-surface-hover cursor-pointer text-sm font-medium text-ink-secondary select-none list-none">
                  <span>
                    Otras jugadoras
                    <span className="ml-2 text-xs font-normal text-ink-muted">
                      ({result.marginal_players.length}) — menos del 15% de partidos y media &lt; 5 min — excluidas del análisis
                    </span>
                  </span>
                  <svg className="w-4 h-4 transition-transform group-open:rotate-180" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 10.94L2.06 5l1.41-1.41L8 8.12l4.53-4.53L13.94 5z"/>
                  </svg>
                </summary>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-surface-hover text-ink-secondary">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium">Jugadora</th>
                        <th className="px-3 py-2 text-center font-medium w-12">PJ</th>
                        <th className="px-3 py-2 text-center font-medium w-24">Min. totales</th>
                        <th className="px-3 py-2 text-center font-medium w-24">Min./partido</th>
                        <th className="px-3 py-2 text-center font-medium w-20">% tiempo</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border opacity-70">
                      {result.marginal_players.map(p => (
                        <tr key={p.player_id} className="bg-surface-base hover:bg-surface-hover transition-colors">
                          <td className="px-3 py-2 text-ink-secondary">{p.player_name}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">{p.games_played}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">{fmtNum(p.total_minutes, 1)}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">{fmtNum(p.avg_min_per_game, 1)}</td>
                          <td className="px-3 py-2 text-center text-ink-muted">{fmtPct(p.pct_game_time)}</td>
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
