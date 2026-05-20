/**
 * PredictivePage — Análisis Predictivo
 *
 * Tabs visible al usuario:
 *   1. Proyección MC           — Monte Carlo simulation for N future games
 *   2. Predicción Partido      — Win/Loss probability
 *   3. Predicción Jugador      — per-player next-game Ridge prediction
 *   4. Clasificación Final     — season-end standings projection
 *
 * Tabs técnicas (Admin > Modelos predictivos):
 *   - Elasticidades            — model training + per-team next-game prediction
 *   - Validación               — walk-forward backtesting metrics
 *
 * Ajuste por Rival (descriptivo) → Estadísticas de Equipo > tab "Aj. Rival"
 */
import { useState, useEffect } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { useQuery } from '@tanstack/react-query'
import PageTransition from '@/components/ui/PageTransition'
import {
  getElasticityModels,
  getElasticityPredictLive, postMonteCarlo, getLiveTeamNames,
  getHistoricalSeasons, getHistoricalTeams, getBacktesting, getBacktestingLive, postGamePrediction,
  getPlayerPrediction, getPlayerStats, getSeasonProjection,
  type ElasticityModelMeta,
  type ElasticityPrediction, type MonteCarloResult,
  type HistoricalTeamEntry, type BacktestingResult, type GamePredictionResult,
  type PlayerPredictionResult, type SeasonProjectionEntry, type TeamEntry,
} from '@/api/client'
import { STAT_LABELS } from '@/lib/statLabels'
import { Loader2, Dices, Target, User, Trophy } from 'lucide-react'

// ── helpers ───────────────────────────────────────────────────────────────────
const fmt = (v: number | null | undefined, d = 1) =>
  v == null ? '—' : v.toFixed(d)

const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${(v * 100).toFixed(1)} %`

// ── Shared season + team picker ───────────────────────────────────────────────
function TeamPicker({
  season, teamId,
  onSeasonChange, onTeamChange,
}: {
  season: string
  teamId: string
  onSeasonChange: (s: string) => void
  onTeamChange:   (id: string) => void
}) {
  const { data: seasons = [], isLoading: loadingSeasons } = useQuery({
    queryKey: ['historical-seasons'],
    queryFn:  getHistoricalSeasons,
    staleTime: 60_000,
  })
  const { data: teams = [], isLoading: loadingTeams } = useQuery({
    queryKey: ['historical-teams', season],
    queryFn:  () => getHistoricalTeams(season || undefined),
    enabled:  true,
    staleTime: 60_000,
  })

  // auto-select first season
  useEffect(() => {
    if (!season && seasons.length > 0) onSeasonChange(seasons[0])
  }, [seasons, season, onSeasonChange])

  // clear team when season changes
  useEffect(() => { onTeamChange('') }, [season, onTeamChange])

  return (
    <div className="flex gap-3 flex-wrap items-end">
      <div>
        <label className="block text-xs text-slate-400 mb-1">Temporada</label>
        {loadingSeasons
          ? <div className="h-8 w-28 rounded bg-slate-700 animate-pulse" />
          : seasons.length === 0
            ? <p className="text-xs text-slate-500 italic">Sin datos en HISTORICAL</p>
            : (
              <select
                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-32"
                value={season}
                onChange={e => onSeasonChange(e.target.value)}
              >
                {seasons.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            )
        }
      </div>
      <div>
        <label className="block text-xs text-slate-400 mb-1">Equipo</label>
        {loadingTeams
          ? <div className="h-8 w-52 rounded bg-slate-700 animate-pulse" />
          : teams.length === 0
            ? <p className="text-xs text-slate-500 italic">Sin equipos para esta temporada</p>
            : (
              <select
                className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-56"
                value={teamId}
                onChange={e => onTeamChange(e.target.value)}
              >
                <option value="">Seleccionar equipo…</option>
                {(teams as HistoricalTeamEntry[]).map(t => (
                  <option key={t.team_id} value={t.team_id}>{t.team_name}</option>
                ))}
              </select>
            )
        }
      </div>
    </div>
  )
}

// ── Elasticity tab (Admin > Modelos predictivos) ─────────────────────────────
export function ElasticityTab() {
  const { collection } = useCollection()
  const [models, setModels]     = useState<ElasticityModelMeta[]>([])
  const [training, setTraining] = useState(false)
  const [trainMsg, setTrainMsg] = useState<string | null>(null)
  const [trainProgress, setTrainProgress] = useState<{ step: string; current: number; total: number } | null>(null)
  const [liveTeam, setLiveTeam] = useState('')
  // Optional Modelo B inputs
  const [isHome, setIsHome]         = useState<boolean | null>(null)
  const [oppNetRtg, setOppNetRtg]   = useState('')

  const [pred, setPred]         = useState<ElasticityPrediction | null>(null)
  const [predLoading, setPredLoading] = useState(false)
  const [predError, setPredError]     = useState<string | null>(null)

  const isLiveFbcyl = collection ? collection.name.includes('FBCYL') : false

  const { data: liveTeams = [], isLoading: loadingLiveTeams } = useQuery({
    queryKey: ['live-teams-elasticity', collection?.name],
    queryFn:  () => getLiveTeamNames(collection!.name),
    enabled:  !!collection,
    staleTime: 60_000,
  })

  useEffect(() => {
    getElasticityModels().then(setModels).catch(() => {})
  }, [])

  const handleTrain = async () => {
    setTraining(true)
    setTrainMsg(null)
    setTrainProgress(null)

    try {
      const BASE = (import.meta.env.VITE_API_BASE ?? '') + '/api/v1'
      const res = await fetch(`${BASE}/analysis/elasticity/train/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        // SSE lines are separated by \n\n — process complete events only
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''   // keep incomplete trailing chunk
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.step) {
              // parse "Modelo X — stat (n/total)"
              const m = /\((\d+)\/(\d+)\)/.exec(evt.step)
              setTrainProgress({
                step: evt.step,
                current: m ? parseInt(m[1], 10) : 0,
                total:   m ? parseInt(m[2], 10) : 24,
              })
            }
            if (evt.done) {
              if (evt.error) {
                setTrainMsg(`Error: ${evt.error}`)
              } else {
                const r = evt.result as Record<string, unknown>
                setTrainMsg(`Entrenamiento completado. Stats: ${Object.keys(r).join(', ')}`)
                getElasticityModels().then(setModels).catch(() => {})
              }
            }
          } catch { /* malformed event — skip */ }
        }
      }
    } catch (e: unknown) {
      setTrainMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setTraining(false)
      setTrainProgress(null)
    }
  }

  const handlePredict = () => {
    setPredLoading(true); setPredError(null); setPred(null)
    const oppVal = oppNetRtg !== '' ? parseFloat(oppNetRtg) : undefined
    getElasticityPredictLive(
      collection!.name, liveTeam, isLiveFbcyl,
      isHome ?? undefined,
      Number.isFinite(oppVal) ? oppVal : undefined,
    )
      .then(setPred)
      .catch(e => setPredError(e.message))
      .finally(() => setPredLoading(false))
  }

  const canPredict = !!collection && !!liveTeam

  return (
    <div className="space-y-6">
      {/* Train section */}
      <div className="bg-slate-800/50 rounded-lg p-4 space-y-3">
        <h3 className="font-semibold text-slate-200">Entrenar modelos de elasticidad</h3>
        <p className="text-sm text-slate-400">
          Entrena cuatro modelos con datos de HISTORICAL:{' '}
          <span className="text-slate-300 font-medium">Modelo A</span> (rolling global),{' '}
          <span className="text-slate-300 font-medium">Modelo B</span> (+ local/visitante y rival),{' '}
          <span className="text-slate-300 font-medium">Modelo C</span> (+ ventana larga, momentum y cross-stats) y{' '}
          <span className="text-slate-300 font-medium">Modelo D</span> (GBM con intervalos cuantílicos).
          Requiere haber ejecutado la ingesta histórica previamente.
        </p>
        <button
          onClick={handleTrain}
          disabled={training}
          className="btn-primary flex items-center gap-2"
        >
          {training && <Loader2 className="animate-spin w-4 h-4" />}
          {training ? 'Entrenando…' : 'Entrenar modelos (Ridge A/B/C + GBM D)'}
        </button>

        {/* Live progress */}
        {training && (
          <div className="space-y-1.5">
            <div className="w-full bg-slate-700 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-brand-500 h-1.5 rounded-full transition-all duration-300"
                style={{ width: trainProgress ? `${(trainProgress.current / trainProgress.total) * 100}%` : '0%' }}
              />
            </div>
            <p className="text-xs text-slate-400 font-mono">
              {trainProgress ? trainProgress.step : 'Iniciando entrenamiento…'}
            </p>
          </div>
        )}

        {trainMsg && <p className="text-sm text-brand-400">{trainMsg}</p>}
      </div>

      {/* Models list */}
      {models.length > 0 && (
        <div>
          <h3 className="font-semibold text-slate-200 mb-2">Modelos almacenados</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-slate-200 border-collapse">
              <thead>
                <tr className="bg-slate-700 text-slate-300">
                  <th className="px-3 py-2 text-left">Tipo</th>
                  <th className="px-3 py-2 text-left">Stat</th>
                  <th className="px-3 py-2 text-left">Liga</th>
                  <th className="px-3 py-2 text-right">R²</th>
                  <th className="px-3 py-2 text-right">Muestras</th>
                  <th className="px-3 py-2 text-right">Equipos</th>
                </tr>
              </thead>
              <tbody>
                {models.map(m => (
                  <tr key={`${m.model_type}-${m.stat}`} className="border-t border-slate-700">
                    <td className="px-3 py-1.5 font-mono text-brand-400">Modelo {m.model_type}</td>
                    <td className="px-3 py-1.5">{STAT_LABELS[m.stat]?.label ?? m.stat}</td>
                    <td className="px-3 py-1.5 text-slate-400">{m.league}</td>
                    <td className="px-3 py-1.5 text-right">{fmt(m.r2_train, 3)}</td>
                    <td className="px-3 py-1.5 text-right">{m.n_samples}</td>
                    <td className="px-3 py-1.5 text-right">{m.n_teams}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Prediction section */}
      <div className="bg-slate-800/50 rounded-lg p-4 space-y-3">
        <h3 className="font-semibold text-slate-200">Predecir próximo partido</h3>

        <div className="flex gap-3 flex-wrap items-end">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Equipo</label>
            {loadingLiveTeams
              ? <div className="h-8 w-52 rounded bg-slate-700 animate-pulse" />
              : !collection
                ? <p className="text-xs text-slate-500 italic">Selecciona una colección primero</p>
                : liveTeams.length === 0
                  ? <p className="text-xs text-slate-500 italic">Sin equipos en esta colección</p>
                  : (
                    <select
                      className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-56"
                      value={liveTeam}
                      onChange={e => setLiveTeam(e.target.value)}
                    >
                      <option value="">Seleccionar equipo…</option>
                      {liveTeams.map(t => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                  )
            }
          </div>
          <button onClick={handlePredict} disabled={predLoading || !canPredict} className="btn-primary">
            {predLoading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Predecir'}
          </button>
        </div>

        {/* Optional Modelo B inputs */}
        <div className="flex gap-4 flex-wrap items-end pt-1">
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              ¿Local o visitante? <span className="text-slate-500">(opcional — activa Modelo B)</span>
            </label>
            <div className="flex gap-1">
              {([null, true, false] as const).map(v => (
                <button
                  key={String(v)}
                  onClick={() => setIsHome(v)}
                  className={`px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
                    isHome === v
                      ? 'bg-brand-600 border-brand-500 text-white'
                      : 'bg-slate-700 border-slate-600 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {v === null ? 'Sin especificar' : v ? 'Local' : 'Visitante'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Net Rating rival <span className="text-slate-500">(opcional)</span></label>
            <input
              type="number"
              step="0.1"
              placeholder="p.ej. -2.5"
              value={oppNetRtg}
              onChange={e => setOppNetRtg(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-36"
            />
          </div>
        </div>
        {predError && <p className="text-red-400 text-sm">{predError}</p>}

        {pred && (() => {
          const hasModelB = Object.values(pred).some(v => v.model_b)
          return (
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm text-slate-200 border-collapse">
              <thead>
                <tr className="bg-slate-700 text-slate-300">
                  <th className="px-3 py-2 text-left">Estadística</th>
                  <th className="px-3 py-2 text-right">Modelo A (estimación)</th>
                  <th className="px-3 py-2 text-right">IC 90% (A)</th>
                  {hasModelB && <th className="px-3 py-2 text-right">Modelo B (estimación)</th>}
                  {hasModelB && <th className="px-3 py-2 text-right">IC 90% (B)</th>}
                </tr>
              </thead>
              <tbody>
                {Object.entries(pred).map(([stat, v]) => (
                  <tr key={stat} className="border-t border-slate-700">
                    <td className="px-3 py-1.5 font-medium">{STAT_LABELS[stat]?.label ?? stat}</td>
                    <td className="px-3 py-1.5 text-right font-semibold text-brand-300">
                      {v.model_a ? fmt(v.model_a.estimate) : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right text-slate-400">
                      {v.model_a ? `[${fmt(v.model_a.ci_low)}, ${fmt(v.model_a.ci_high)}]` : '—'}
                    </td>
                    {hasModelB && (
                      <td className="px-3 py-1.5 text-right font-semibold text-accent-300">
                        {v.model_b ? fmt(v.model_b.estimate) : '—'}
                      </td>
                    )}
                    {hasModelB && (
                      <td className="px-3 py-1.5 text-right text-slate-400">
                        {v.model_b ? `[${fmt(v.model_b.ci_low)}, ${fmt(v.model_b.ci_high)}]` : '—'}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )
        })()}
      </div>
    </div>
  )
}

// ── Monte Carlo tab ───────────────────────────────────────────────────────────
type MCSource = 'historical' | 'live'

function MonteCarloTab() {
  const { collection } = useCollection()
  const [source, setSource]    = useState<MCSource>('historical')

  // Historical mode state
  const [teamId, setTeamId]    = useState('')
  const [season, setSeason]    = useState('')

  // Live mode state
  const [liveTeam, setLiveTeam] = useState('')

  // Shared simulation params
  const [nGames, setNGames]    = useState(5)
  const [nSims, setNSims]      = useState(1000)
  const [result, setResult]    = useState<MonteCarloResult | null>(null)
  const [loading, setLoading]  = useState(false)
  const [error, setError]      = useState<string | null>(null)

  const isLiveFbcyl = collection ? collection.name.includes('FBCYL') : false

  const { data: liveTeams = [], isLoading: loadingLiveTeams } = useQuery({
    queryKey: ['live-teams', collection?.name],
    queryFn:  () => getLiveTeamNames(collection!.name),
    enabled:  source === 'live' && !!collection,
    staleTime: 60_000,
  })

  // Reset results when switching source
  const handleSourceChange = (s: MCSource) => {
    setSource(s); setResult(null); setError(null)
    setLiveTeam(''); setTeamId(''); setSeason('')
  }

  const canSimulate = source === 'historical'
    ? !!teamId && !!season
    : !!liveTeam

  const handleSimulate = () => {
    if (!canSimulate) return
    setLoading(true); setError(null); setResult(null)

    const commonParams = { n_games: nGames, n_simulations: nSims }

    const req = source === 'live'
      ? {
          ...commonParams,
          live_collection: collection!.name,
          live_team_id:    liveTeam,
          live_is_fbcyl:   isLiveFbcyl,
        }
      : { ...commonParams, season }

    const idForUrl = source === 'live'
      ? encodeURIComponent(liveTeam)
      : teamId

    postMonteCarlo(idForUrl, req)
      .then(setResult)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  return (
    <div className="space-y-6">
      {/* Config */}
      <div className="bg-slate-800/50 rounded-lg p-4 space-y-4">
        <h3 className="font-semibold text-slate-200">Configurar simulación</h3>

        {/* Source toggle */}
        <div>
          <label className="block text-xs text-slate-400 mb-1">Fuente de datos</label>
          <div className="inline-flex rounded-lg border border-slate-600 overflow-hidden text-sm">
            {(['historical', 'live'] as MCSource[]).map(s => (
              <button
                key={s}
                onClick={() => handleSourceChange(s)}
                className={`px-4 py-1.5 transition-colors ${
                  source === s
                    ? 'bg-brand-600 text-white font-medium'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {s === 'historical' ? 'Temporadas anteriores' : 'Temporada actual'}
              </button>
            ))}
          </div>
          {source === 'live' && (
            <p className="text-xs text-slate-500 mt-1">
              Usa los partidos jugados esta temporada en la colección activa.
              Los modelos entrenados en HISTÓRICO no se ven afectados.
            </p>
          )}
        </div>

        {/* Team picker */}
        <div className="flex gap-3 flex-wrap items-end">
          {source === 'historical' ? (
            <TeamPicker
              season={season} teamId={teamId}
              onSeasonChange={setSeason} onTeamChange={setTeamId}
            />
          ) : (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Equipo</label>
              {loadingLiveTeams
                ? <div className="h-8 w-52 rounded bg-slate-700 animate-pulse" />
                : liveTeams.length === 0
                  ? <p className="text-xs text-slate-500 italic">Sin equipos en esta colección</p>
                  : (
                    <select
                      className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-56"
                      value={liveTeam}
                      onChange={e => setLiveTeam(e.target.value)}
                    >
                      <option value="">Seleccionar equipo…</option>
                      {liveTeams.map((t: TeamEntry) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  )
              }
            </div>
          )}

          <div>
            <label className="block text-xs text-slate-400 mb-1">Partidos a proyectar</label>
            <input
              type="number" min={1} max={10}
              className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-20"
              value={nGames}
              onChange={e => setNGames(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Simulaciones</label>
            <select
              className="bg-slate-700 border border-slate-600 rounded px-3 py-1.5 text-sm text-white"
              value={nSims}
              onChange={e => setNSims(Number(e.target.value))}
            >
              {[100, 500, 1000, 2000, 5000].map(n => (
                <option key={n} value={n}>{n.toLocaleString()}</option>
              ))}
            </select>
          </div>
          <button onClick={handleSimulate} disabled={loading || !canSimulate} className="btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="animate-spin w-4 h-4" /> : <Dices className="w-4 h-4" />}
            {loading ? 'Simulando…' : 'Simular'}
          </button>
        </div>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary card */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: 'Victorias proyectadas (media)', value: fmt(result.projected_wins_mean, 1) },
              { label: 'Desv. estándar', value: fmt(result.projected_wins_std, 2) },
              { label: 'IC 90% inferior', value: fmt(result.projected_wins_ci_low, 1) },
              { label: 'IC 90% superior', value: fmt(result.projected_wins_ci_high, 1) },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-brand-400">{value}</p>
                <p className="text-xs text-slate-400 mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* Per-game table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-slate-200 border-collapse">
              <thead>
                <tr className="bg-slate-700 text-slate-300">
                  <th className="px-3 py-2 text-left">Partido</th>
                  <th className="px-3 py-2 text-center">Local/Visit.</th>
                  <th className="px-3 py-2 text-right">P(victoria)</th>
                  {result.games[0] && Object.keys(result.games[0].stats).map(s => (
                    <th key={s} className="px-3 py-2 text-right">{STAT_LABELS[s]?.label ?? s}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.games.map(g => (
                  <tr key={g.game_index} className="border-t border-slate-700">
                    <td className="px-3 py-1.5 text-center font-medium">#{g.game_index}</td>
                    <td className="px-3 py-1.5 text-center text-slate-400">
                      {g.is_home === null ? '—' : g.is_home ? 'Local' : 'Visitante'}
                    </td>
                    <td className={`px-3 py-1.5 text-right font-semibold ${
                      g.win_prob >= 0.5 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {pct(g.win_prob)}
                    </td>
                    {Object.entries(g.stats).map(([s, sv]) => (
                      <td key={s} className="px-3 py-1.5 text-right">
                        <span className="font-medium">{fmt(sv.mean)}</span>
                        <span className="text-slate-500 text-xs ml-1">
                          [{fmt(sv.ci_low)}, {fmt(sv.ci_high)}]
                        </span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Friendly labels for classifier feature names ─────────────────────────────
const FEAT_LABELS: Record<string, string> = {
  roll3_net_rtg:   'Net Rtg (últ. 3 j.)',
  roll5_net_rtg:   'Net Rtg (últ. 5 j.)',
  roll10_net_rtg:  'Net Rtg (últ. 10 j.)',
  roll3_efg_pct:   'eFG% (últ. 3 j.)',
  roll5_efg_pct:   'eFG% (últ. 5 j.)',
  roll10_efg_pct:  'eFG% (últ. 10 j.)',
  roll3_tov_rate:  'TOV% (últ. 3 j.)',
  roll5_tov_rate:  'TOV% (últ. 5 j.)',
  roll10_tov_rate: 'TOV% (últ. 10 j.)',
  is_home:         'Ventaja local',
  opp_bucket:      'Fortaleza rival',
}

// ── Game Prediction tab (FASE 7 — Win/Loss classifier) ────────────────────
function GamePredictionTab() {
  const { collection } = useCollection()
  const isLiveFbcyl = collection ? collection.name.includes('FBCYL') : false

  const [mode, setMode] = useState<'historical' | 'live'>('historical')

  const [seasons, setSeasons]     = useState<string[]>([])
  const [teams, setTeams]         = useState<HistoricalTeamEntry[]>([])
  const [season, setSeason]       = useState('')
  const [teamId, setTeamId]       = useState('')

  const [liveTeams, setLiveTeams] = useState<TeamEntry[]>([])
  const [liveTeam, setLiveTeam]   = useState('')

  const [isHome, setIsHome]       = useState(true)
  const [oppNetRtg, setOppNetRtg] = useState('')
  const [result, setResult]       = useState<GamePredictionResult | null>(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)

  useEffect(() => {
    getHistoricalSeasons().then(s => {
      setSeasons(s)
      if (s.length) setSeason(s[0])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!season) return
    getHistoricalTeams(season).then(t => {
      setTeams(t)
      if (t.length) setTeamId(t[0].team_id)
    }).catch(() => {})
  }, [season])

  useEffect(() => {
    if (mode !== 'live' || !collection) return
    getLiveTeamNames(collection.name).then(t => {
      setLiveTeams(t)
      if (t.length) setLiveTeam(t[0].id)
    }).catch(() => {})
  }, [mode, collection])

  const run = async () => {
    if (mode === 'historical' && (!teamId || !season)) return
    if (mode === 'live' && (!liveTeam || !collection)) return
    setLoading(true); setError(null); setResult(null)
    const opp = oppNetRtg !== '' ? parseFloat(oppNetRtg) : 0
    try {
      const r = await postGamePrediction(
        mode === 'live' ? '_live' : teamId,
        mode === 'live'
          ? { live_collection: collection!.name, live_team_id: liveTeam, live_is_fbcyl: isLiveFbcyl, is_home: isHome, opp_net_rtg: Number.isFinite(opp) ? opp : 0 }
          : { season, is_home: isHome, opp_net_rtg: Number.isFinite(opp) ? opp : 0 },
      )
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const inputCls = 'bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 outline-none'
  const probColor = (p: number) =>
    p >= 0.6 ? 'text-emerald-400' : p <= 0.4 ? 'text-red-400' : 'text-amber-400'

  const sortedImportances = result
    ? Object.entries(result.feature_importances).sort(([, a], [, b]) => b - a).slice(0, 9)
    : []

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-white mb-1">Predicción Victoria/Derrota</h3>
        <p className="text-xs text-slate-400">
          Regresión Logística calibrada entrenada sobre el historial de la temporada.
          Usa rolling-window de Net Rtg, eFG% y TOV% más contexto local/visitante y fuerza del rival.
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2">
        {(['historical', 'live'] as const).map(m => (
          <button
            key={m}
            onClick={() => { setMode(m); setResult(null); setError(null) }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === m
                ? 'bg-brand-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {m === 'historical' ? 'Temporada histórica' : 'Temporada actual'}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
        {mode === 'historical' ? (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Temporada</label>
              <select className={inputCls} value={season} onChange={e => setSeason(e.target.value)}>
                {seasons.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Equipo</label>
              <select className={inputCls} value={teamId} onChange={e => setTeamId(e.target.value)}>
                {teams.map(t => <option key={t.team_id} value={t.team_id}>{t.team_name}</option>)}
              </select>
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Equipo (temporada actual)</label>
            {collection
              ? (
                <select className={inputCls + ' w-64'} value={liveTeam} onChange={e => setLiveTeam(e.target.value)}>
                  {(liveTeams as TeamEntry[]).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              )
              : <p className="text-xs text-slate-500 italic">Selecciona una colección primero</p>
            }
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Campo</label>
          <select className={inputCls} value={isHome ? 'home' : 'away'}
            onChange={e => setIsHome(e.target.value === 'home')}>
            <option value="home">Local</option>
            <option value="away">Visitante</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Net Rtg rival</label>
          <input
            type="number"
            className={inputCls + ' w-28'}
            placeholder="0.0"
            value={oppNetRtg}
            onChange={e => setOppNetRtg(e.target.value)}
          />
        </div>
        <button
          onClick={run}
          disabled={loading || (mode === 'historical' ? !teamId : !liveTeam)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          {loading ? 'Calculando…' : 'Predecir'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-900/30 border border-red-700/50 p-3 text-red-300 text-sm">{error}</div>
      )}

      {result && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Probability card */}
          <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-5 flex flex-col items-center gap-3">
            <span className="text-xs text-slate-400 uppercase tracking-wider">P(Victoria)</span>
            <span className={`text-5xl font-bold tabular-nums ${probColor(result.win_prob)}`}>
              {(result.win_prob * 100).toFixed(1)}&thinsp;%
            </span>
            <span className="text-xs text-slate-400">
              IC 90 %: {(result.ci_low * 100).toFixed(1)} % – {(result.ci_high * 100).toFixed(1)} %
            </span>
            <div className="w-full bg-slate-700 rounded-full h-2 mt-1">
              <div
                className="h-2 rounded-full bg-brand-500 transition-all"
                style={{ width: `${result.win_prob * 100}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3 w-full text-center mt-1">
              <div>
                <p className="text-xs text-slate-400">Partidos entrenados</p>
                <p className="text-sm font-semibold text-white">{result.n_train}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Accuracy walk-fwd</p>
                <p className="text-sm font-semibold text-white">
                  {result.accuracy != null ? `${(result.accuracy * 100).toFixed(1)} %` : '—'}
                </p>
              </div>
            </div>
          </div>

          {/* Feature importances with sign */}
          <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-5">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Importancia de variables
            </h4>
            <p className="text-xs text-slate-500 mb-3">
              <span className="text-emerald-400">Verde</span> = favorece la victoria · 
              <span className="text-red-400">Rojo</span> = la perjudica
            </p>
            <div className="space-y-2.5">
              {sortedImportances.map(([name, absVal]) => {
                const coef = result.feature_coefficients?.[name] ?? absVal
                const positive = coef >= 0
                const barColor = positive ? 'bg-emerald-500' : 'bg-red-500'
                const label = FEAT_LABELS[name] ?? name
                return (
                  <div key={name}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-slate-300">{label}</span>
                      <span className={positive ? 'text-emerald-400' : 'text-red-400'}>
                        {positive ? '+' : '−'}{(absVal * 100).toFixed(1)} %
                      </span>
                    </div>
                    <div className="w-full bg-slate-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full ${barColor} transition-all`}
                        style={{ width: `${absVal * 100}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Validation tab (Admin > Modelos predictivos) ────────────────────────────
export function ValidationTab() {
  const { collection } = useCollection()

  // mode toggle
  const [mode, setMode]         = useState<'historical' | 'live'>('historical')

  // historical mode state
  const [seasons, setSeasons]   = useState<string[]>([])
  const [teams, setTeams]       = useState<HistoricalTeamEntry[]>([])
  const [season, setSeason]     = useState('')
  const [teamId, setTeamId]     = useState('')

  // live mode state
  const [liveTeams, setLiveTeams] = useState<TeamEntry[]>([])
  const [liveTeam, setLiveTeam]   = useState('')

  const [result, setResult]     = useState<BacktestingResult | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  // load historical seasons
  useEffect(() => {
    if (mode !== 'historical') return
    getHistoricalSeasons().then(s => {
      setSeasons(s)
      if (s.length) setSeason(s[0])
    }).catch(() => {})
  }, [mode])

  // load historical teams when season changes
  useEffect(() => {
    if (mode !== 'historical' || !season) return
    getHistoricalTeams(season).then(t => {
      setTeams(t)
      if (t.length) setTeamId(t[0].team_id)
    }).catch(() => {})
  }, [season, mode])

  // load live team names when switching to live mode
  useEffect(() => {
    if (mode !== 'live' || !collection?.name) return
    getLiveTeamNames(collection.name).then(names => {
      setLiveTeams(names)
      if (names.length) setLiveTeam(names[0].id)
    }).catch(() => {})
  }, [mode, collection?.name])

  const run = async () => {
    setLoading(true); setError(null); setResult(null)
    try {
      if (mode === 'historical') {
        if (!teamId || !season) return
        const r = await getBacktesting(teamId, season)
        setResult(r)
      } else {
        if (!liveTeam || !collection?.name) return
        const isFbcyl = collection.name.toUpperCase().includes('FBCYL')
        const r = await getBacktestingLive(collection.name, liveTeam, isFbcyl)
        setResult(r)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const inputCls = 'bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 outline-none'
  const colHdr   = 'text-right text-xs text-slate-400 font-semibold py-2 px-3'
  const cell     = (v: number | null | undefined, d = 2) =>
    v == null ? '—' : v.toFixed(d)

  // Stats for which MAPE is suppressed (net_rtg oscillates near zero)
  const MAPE_SUPPRESSED = new Set(['net_rtg'])

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-white mb-1">Validación Walk-Forward</h3>
        <p className="text-xs text-slate-400">
          Evalúa la precisión de los modelos Ridge entrenando sólo con datos pasados
          y midiendo el error en cada partido sucesivo (sin fuga de datos futuros).
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2">
        {(['historical', 'live'] as const).map(m => (
          <button
            key={m}
            onClick={() => { setMode(m); setResult(null) }}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              mode === m
                ? 'bg-brand-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'
            }`}
          >
            {m === 'historical' ? 'Temporada histórica' : 'Temporada actual'}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
        {mode === 'historical' ? (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Temporada</label>
              <select className={inputCls} value={season} onChange={e => setSeason(e.target.value)}>
                {seasons.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-slate-400">Equipo</label>
              <select className={inputCls} value={teamId} onChange={e => setTeamId(e.target.value)}>
                {teams.map(t => <option key={t.team_id} value={t.team_id}>{t.team_name}</option>)}
              </select>
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Equipo — {collection?.name ?? '…'}</label>
            <select className={inputCls} value={liveTeam} onChange={e => setLiveTeam(e.target.value)}>
              {liveTeams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        )}
        <button
          onClick={run}
          disabled={loading || (mode === 'historical' ? !teamId : !liveTeam)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          {loading ? 'Calculando…' : 'Ejecutar backtesting'}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-900/30 border border-red-700/50 p-3 text-red-300 text-sm">{error}</div>
      )}

      {/* Results table */}
      {result && Object.keys(result).length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-700/50">
          <table className="w-full text-sm text-slate-200 border-collapse">
            <thead className="bg-slate-800/80">
              <tr>
                <th className="text-left text-xs text-slate-400 font-semibold py-2 px-3">Stat</th>
                <th className={colHdr}>Modelo</th>
                <th className={colHdr}>MAE</th>
                <th className={colHdr}>RMSE</th>
                <th className={colHdr}>MAPE %</th>
                <th className={colHdr} title="MAE del modelo dividido entre MAE naive. <1 = modelo mejor que naive">MAE/naive</th>
                <th className={colHdr}>Partidos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/40">
              {Object.entries(result).flatMap(([stat, models]) => {
                const showMape = !MAPE_SUPPRESSED.has(stat)
                const naiveMae = models.naive?.mae ?? null
                const rows = (['model_a', 'model_b', 'naive'] as const).map(mk => {
                  const m = models[mk]
                  if (!m) return null
                  const isNaive = mk === 'naive'
                  const modelMae = 'mae' in m ? m.mae : null
                  const ratio = !isNaive && modelMae != null && naiveMae != null && naiveMae > 0
                    ? modelMae / naiveMae
                    : null
                  const ratioCls = ratio == null
                    ? 'text-slate-500'
                    : ratio < 0.95 ? 'text-green-400 font-semibold'
                    : ratio > 1.05 ? 'text-red-400'
                    : 'text-slate-400'
                  return (
                    <tr key={`${stat}-${mk}`} className={`hover:bg-slate-800/40 ${isNaive ? 'bg-slate-800/20' : ''}`}>
                      {mk === 'model_a' && (
                        <td rowSpan={3} className="px-3 py-2 font-medium text-slate-300 align-middle border-r border-slate-700/40">
                          {STAT_LABELS[stat]?.label ?? stat}
                        </td>
                      )}
                      <td className="px-3 py-1 text-right text-slate-400 text-xs">
                        {mk === 'model_a' ? 'A (global)' : mk === 'model_b' ? 'B (cond.)' : 'Naive (media)'}
                      </td>
                      <td className="px-3 py-1 text-right tabular-nums">{cell(modelMae)}</td>
                      <td className="px-3 py-1 text-right tabular-nums">{cell('rmse' in m ? m.rmse : undefined)}</td>
                      <td className="px-3 py-1 text-right tabular-nums text-slate-500">
                        {isNaive || !showMape
                          ? '—'
                          : ('mape' in m && m.mape != null ? `${m.mape.toFixed(1)} %` : '—')
                        }
                      </td>
                      <td className={`px-3 py-1 text-right tabular-nums ${ratioCls}`}>
                        {ratio == null ? '—' : ratio.toFixed(2)}
                      </td>
                      <td className="px-3 py-1 text-right tabular-nums text-slate-400">{m.n_evaluated}</td>
                    </tr>
                  )
                })
                return rows
              })}
            </tbody>
          </table>
          <div className="px-3 py-2 flex gap-4 text-xs text-slate-500">
            <span><span className="text-green-400 font-semibold">Verde</span> = modelo mejor que naive (&lt;0.95)</span>
            <span><span className="text-red-400">Rojo</span> = naive mejor que modelo (&gt;1.05)</span>
            {Object.keys(result).some(s => MAPE_SUPPRESSED.has(s)) && (
              <span>· MAPE omitido para <span className="font-mono">net_rtg</span> (oscila cerca de cero)</span>
            )}
          </div>
        </div>
      )}

      {result && Object.keys(result).length === 0 && (
        <p className="text-slate-400 text-sm">
          Sin datos suficientes para este equipo y temporada (mínimo {mode === 'live' ? 'temporada actual' : 'HISTORICAL'}).
        </p>
      )}
    </div>
  )
}

// ── FASE 9 — Season Projection tab ──────────────────────────────────────────
function SeasonProjectionTab() {
  const { collection } = useCollection()
  const collectionName = collection?.name ?? ''
  const isFbcyl = collectionName.toUpperCase().includes('FBCYL')

  const [seasonLength, setSeasonLength] = useState(22)
  const [submitted, setSubmitted] = useState<{ seasonLength: number } | null>(null)

  const { data, isFetching, error } = useQuery({
    queryKey: ['seasonProjection', collectionName, submitted],
    queryFn: () => getSeasonProjection(
      collectionName, submitted!.seasonLength, 1000, 4, isFbcyl
    ),
    enabled: !!submitted && !!collectionName,
    retry: false,
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitted({ seasonLength })
  }

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white">Proyección de Clasificación Final</h2>
      <p className="text-slate-400 text-sm">
        Proyección Monte Carlo de la clasificación final de la liga simulando los partidos
        restantes usando modelos de net rating. Muestra victorias proyectadas, probabilidad
        de playoff y distribución de posiciones para cada equipo.
      </p>

      {!collectionName && (
        <p className="text-slate-500 text-sm italic">Selecciona una colección primero.</p>
      )}

      {collectionName && (
        <form onSubmit={handleSubmit} className="flex flex-wrap gap-4 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">Partidos/temporada</label>
            <input
              type="number"
              value={seasonLength}
              onChange={e => setSeasonLength(Number(e.target.value))}
              min={1} max={40}
              className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-20"
            />
          </div>

          <button
            type="submit"
            disabled={isFetching}
            className="px-5 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded disabled:opacity-50"
          >
            {isFetching ? <Loader2 className="w-4 h-4 animate-spin inline" /> : 'Proyectar'}
          </button>
        </form>
      )}

      {error && (
        <p className="text-red-400 text-sm">
          {error instanceof Error ? error.message : 'Error al obtener proyección'}
        </p>
      )}

      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-slate-200 border-collapse">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700">
                <th className="text-left py-2 px-3">#</th>
                <th className="text-left py-2 px-3">Equipo</th>
                <th className="text-right py-2 px-3">V-D act.</th>
                <th className="text-right py-2 px-3">V proy.</th>
                <th className="text-right py-2 px-3">IC 90%</th>
                <th className="text-right py-2 px-3">P(Playoff)</th>
                <th className="text-right py-2 px-3">P(1º)</th>
              </tr>
            </thead>
            <tbody>
              {data.map((entry: SeasonProjectionEntry, idx: number) => (
                <tr key={entry.team_id} className="border-b border-slate-800 hover:bg-slate-800/30">
                  <td className="py-2 px-3 text-slate-400">{idx + 1}</td>
                  <td className="py-2 px-3 font-medium">{entry.team_name}</td>
                  <td className="py-2 px-3 text-right">
                    {entry.wins_so_far}-{entry.losses_so_far}
                  </td>
                  <td className="py-2 px-3 text-right font-semibold">
                    {fmt(entry.proj_wins)}
                  </td>
                  <td className="py-2 px-3 text-right text-slate-400 text-xs">
                    {fmt(entry.proj_wins_ci_low)}–{fmt(entry.proj_wins_ci_high)}
                  </td>
                  <td className={`py-2 px-3 text-right font-semibold ${
                    entry.playoff_prob >= 0.7 ? 'text-green-400' :
                    entry.playoff_prob >= 0.4 ? 'text-amber-400' : 'text-red-400'
                  }`}>
                    {pct(entry.playoff_prob)}
                  </td>
                  <td className="py-2 px-3 text-right text-slate-300">
                    {pct(entry.rank_probs?.[1] ?? 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── FASE 8 — Player Prediction tab ──────────────────────────────────────────
function PlayerPredictionTab() {
  const { collection } = useCollection()
  const collectionName = collection?.name ?? ''
  const [teamFilter, setTeamFilter] = useState('')
  const [playerId, setPlayerId] = useState('')
  const [_playerName, setPlayerName] = useState('')
  const [isHome, setIsHome] = useState(true)
  const [oppNetRtg, setOppNetRtg] = useState('')
  const [submitted, setSubmitted] = useState<{
    playerId: string; isHome: boolean; oppNetRtg: number
  } | null>(null)

  // Fetch player list for autocomplete
  const { data: players } = useQuery({
    queryKey: ['playerStats', collectionName],
    queryFn: () => getPlayerStats(collectionName),
    enabled: !!collectionName,
  })

  // Derive unique sorted team names from player list
  const teamNames = Array.from(new Set((players ?? []).map(p => p.team_name))).sort()

  // Players filtered by selected team
  const filteredPlayers = teamFilter
    ? (players ?? []).filter(p => p.team_name === teamFilter)
    : (players ?? [])

  // Reset player when team filter changes
  const handleTeamFilter = (name: string) => {
    setTeamFilter(name)
    setPlayerId('')
  }

  const { data, isFetching, error } = useQuery({
    queryKey: ['playerPrediction', collectionName, submitted],
    queryFn: () => getPlayerPrediction(
      collectionName,
      submitted!.playerId,
      submitted!.isHome,
      submitted!.oppNetRtg,
    ),
    enabled: !!submitted && !!collectionName,
    retry: false,
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!playerId) return
    const opp = oppNetRtg !== '' ? parseFloat(oppNetRtg) : 0
    setSubmitted({ playerId, isHome, oppNetRtg: Number.isFinite(opp) ? opp : 0 })
  }

  const statLabels: Record<keyof PlayerPredictionResult, string> = {
    pts: 'Puntos',
    reb: 'Rebotes',
    ast: 'Asistencias',
    val: 'Valoración',
  }

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-white">Predicción por Jugador</h2>
      <p className="text-slate-400 text-sm">
        Predicción del próximo partido de un jugador usando regresión Ridge sobre su historial
        de la temporada actual en la colección seleccionada.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-wrap gap-4 items-end">
        {/* Team filter */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Equipo</label>
          <select
            value={teamFilter}
            onChange={e => handleTeamFilter(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-48"
          >
            <option value="">— Todos —</option>
            {teamNames.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        {/* Player selector */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Jugador</label>
          <select
            value={playerId}
            onChange={e => {
              const found = filteredPlayers.find(p => p.player_id === e.target.value)
              setPlayerId(e.target.value)
              setPlayerName(found?.player_name ?? '')
            }}
            className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-56"
          >
            <option value="">— Selecciona jugador —</option>
            {filteredPlayers.map(p => (
              <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
            ))}
          </select>
        </div>

        {/* Home/Away */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Local / Visitante</label>
          <select
            value={isHome ? 'home' : 'away'}
            onChange={e => setIsHome(e.target.value === 'home')}
            className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white"
          >
            <option value="home">Local</option>
            <option value="away">Visitante</option>
          </select>
        </div>

        {/* Opponent net rating */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Net Rtg rival</label>
          <input
            type="number"
            value={oppNetRtg}
            onChange={e => setOppNetRtg(e.target.value)}
            placeholder="0.0"
            className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white w-24"
          />
        </div>

        <button
          type="submit"
          disabled={!playerId || isFetching}
          className="px-5 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded disabled:opacity-50"
        >
          {isFetching ? <Loader2 className="w-4 h-4 animate-spin inline" /> : 'Predecir'}
        </button>
      </form>

      {error && (
        <p className="text-red-400 text-sm">
          {error instanceof Error ? error.message : 'Error al obtener predicción'}
        </p>
      )}

      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
          {(Object.keys(statLabels) as Array<keyof PlayerPredictionResult>).map(stat => {
            const s = data[stat]
            const hasValue = s.estimate != null
            return (
              <div key={stat} className="bg-slate-800/60 rounded-lg p-4 space-y-1 border border-slate-700/50">
                <p className="text-xs text-slate-400 uppercase tracking-wider">{statLabels[stat]}</p>
                <p className="text-3xl font-bold text-white">
                  {hasValue ? fmt(s.estimate) : '—'}
                </p>
                {hasValue && (
                  <p className="text-xs text-slate-400">
                    IC 90%: {fmt(s.ci_low)} – {fmt(s.ci_high)}
                  </p>
                )}
                <p className="text-xs text-slate-500">n={s.n_train} partidos</p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
type Tab = 'montecarlo' | 'prediction' | 'player' | 'season'

const TABS: Array<{ id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'montecarlo',  label: 'Proyección MC',       icon: Dices },
  { id: 'prediction',  label: 'Predicción Partido',  icon: Target },
  { id: 'player',      label: 'Predicción Jugador',  icon: User },
  { id: 'season',      label: 'Clasificación Final', icon: Trophy },
]

export default function PredictivePage() {
  const [tab, setTab] = useState<Tab>('montecarlo')

  return (
    <PageTransition>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Análisis Predictivo</h1>
          <p className="text-slate-400 text-sm mt-1">
            Estadísticas ajustadas por rival · Modelos Ridge + Bootstrap · Proyección Monte Carlo · Validación walk-forward
          </p>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 bg-slate-800/60 rounded-lg p-1 w-fit">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === id
                  ? 'bg-brand-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-slate-900/50 rounded-xl border border-slate-700/50 p-6">
          {tab === 'montecarlo' && <MonteCarloTab />}
          {tab === 'prediction' && <GamePredictionTab />}
          {tab === 'player'     && <PlayerPredictionTab />}
          {tab === 'season'     && <SeasonProjectionTab />}
        </div>
      </div>
    </PageTransition>
  )
}
