/**
 * PredictivePage — Análisis Predictivo (FASE 2-6)
 *
 * Tabs:
 *   1. Ajuste por Rival   — rival-adjusted stats for all teams this season
 *   2. Elasticidades      — model training + per-team next-game prediction
 *   3. Proyección MC      — Monte Carlo simulation for N future games
 *   4. Validación         — walk-forward backtesting metrics (FASE 6)
 */
import { useState, useEffect } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { useQuery } from '@tanstack/react-query'
import PageTransition from '@/components/ui/PageTransition'
import {
  getRivalAdjusted, getElasticityModels, postTrainElasticity,
  getElasticityPredict, postMonteCarlo, getLiveTeamNames,
  getHistoricalSeasons, getHistoricalTeams, getBacktesting, postGamePrediction,
  type RivalAdjustedResult, type ElasticityModelMeta,
  type ElasticityPrediction, type MonteCarloResult,
  type HistoricalTeamEntry, type BacktestingResult, type GamePredictionResult,
} from '@/api/client'
import { Loader2, TrendingUp, BarChart2, Dices, FlaskConical, Target } from 'lucide-react'

// ── helpers ───────────────────────────────────────────────────────────────────
const fmt = (v: number | null | undefined, d = 1) =>
  v == null ? '—' : v.toFixed(d)

const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${(v * 100).toFixed(1)} %`

const STAT_LABELS: Record<string, string> = {
  net_rtg:   'Net Rating',
  ortg:      'ORtg',
  drtg:      'DRtg',
  efg_pct:   'eFG%',
  tov_rate:  'TOV%',
  oreb_pct:  'OReb%',
}

// ── Rival-adjusted tab ────────────────────────────────────────────────────────
function RivalAdjTab() {
  const { collection } = useCollection()
  const [data, setData]     = useState<RivalAdjustedResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState<string | null>(null)
  const [statKey, setStatKey] = useState('net_rtg')

  useEffect(() => {
    if (!collection) return
    setLoading(true); setError(null)
    getRivalAdjusted(collection.name)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [collection])

  const teams = data ? Object.keys(data) : []
  const tableData = teams
    .map(t => ({ team: t, ...(data![t][statKey] ?? {}) }))
    .filter(r => r.adj_avg != null)
    .sort((a, b) => (b.adj_avg ?? 0) - (a.adj_avg ?? 0))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm font-medium text-slate-300">Estadística:</label>
        <select
          className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white"
          value={statKey}
          onChange={e => setStatKey(e.target.value)}
        >
          {Object.entries(STAT_LABELS).map(([k, l]) => (
            <option key={k} value={k}>{l}</option>
          ))}
        </select>
      </div>

      {loading && <Loader2 className="animate-spin text-brand-400 w-6 h-6" />}
      {error   && <p className="text-red-400 text-sm">{error}</p>}

      {tableData.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-slate-200 border-collapse">
            <thead>
              <tr className="bg-slate-700 text-slate-300">
                <th className="px-3 py-2 text-left">Equipo</th>
                <th className="px-3 py-2 text-right cursor-help" title="Promedio real de la estadística sin ningún ajuste">Media bruta</th>
                <th className="px-3 py-2 text-right cursor-help" title="Corrección aplicada según la dificultad de los rivales enfrentados (modelo Ridge). Positivo = rivales mejor que la media">Ajuste rival</th>
                <th className="px-3 py-2 text-right cursor-help" title="Media bruta + ajuste por rival. Mejor estimador del rendimiento real del equipo independientemente del calendario">Media ajustada</th>
                <th className="px-3 py-2 text-right cursor-help" title="Strength of Schedule: puntuación media de los rivales — cuanto mayor, más difícil el calendario">SOS</th>
                <th className="px-3 py-2 text-right cursor-help" title="Partidos jugados considerados en el cálculo">PJ</th>
              </tr>
            </thead>
            <tbody>
              {tableData.map(r => (
                <tr key={r.team} className="border-t border-slate-700 hover:bg-slate-800/50">
                  <td className="px-3 py-1.5 font-medium">{r.team}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(r.raw_avg)}</td>
                  <td className={`px-3 py-1.5 text-right font-semibold ${
                    (r.adj ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {r.adj != null ? `${r.adj >= 0 ? '+' : ''}${fmt(r.adj)}` : '—'}
                  </td>
                  <td className="px-3 py-1.5 text-right">{fmt(r.adj_avg)}</td>
                  <td className="px-3 py-1.5 text-right text-slate-400">{fmt(r.sos)}</td>
                  <td className="px-3 py-1.5 text-right text-slate-400">{r.n ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && tableData.length === 0 && (
        <p className="text-slate-400 text-sm">Sin datos suficientes para ajuste por rival.</p>
      )}
    </div>
  )
}

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

// ── Elasticity tab ────────────────────────────────────────────────────────────
function ElasticityTab() {
  const [models, setModels]     = useState<ElasticityModelMeta[]>([])
  const [training, setTraining] = useState(false)
  const [trainMsg, setTrainMsg] = useState<string | null>(null)
  const [season, setSeason]     = useState('')
  const [teamId, setTeamId]     = useState('')
  const [pred, setPred]         = useState<ElasticityPrediction | null>(null)
  const [predLoading, setPredLoading] = useState(false)
  const [predError, setPredError]     = useState<string | null>(null)

  useEffect(() => {
    getElasticityModels().then(setModels).catch(() => {})
  }, [])

  const handleTrain = () => {
    setTraining(true); setTrainMsg(null)
    postTrainElasticity({})
      .then(r => {
        setTrainMsg(`Entrenamiento completado. Stats: ${Object.keys(r).join(', ')}`)
        return getElasticityModels()
      })
      .then(setModels)
      .catch(e => setTrainMsg(`Error: ${e.message}`))
      .finally(() => setTraining(false))
  }

  const handlePredict = () => {
    if (!teamId || !season) return
    setPredLoading(true); setPredError(null); setPred(null)
    getElasticityPredict(teamId, season)
      .then(setPred)
      .catch(e => setPredError(e.message))
      .finally(() => setPredLoading(false))
  }

  return (
    <div className="space-y-6">
      {/* Train section */}
      <div className="bg-slate-800/50 rounded-lg p-4 space-y-3">
        <h3 className="font-semibold text-slate-200">Entrenar modelos de elasticidad</h3>
        <p className="text-sm text-slate-400">
          Entrena Modelo A (global) y Modelo B (condicional) con datos de la colección HISTORICAL.
          Requiere haber ejecutado la ingesta histórica previamente.
        </p>
        <button
          onClick={handleTrain}
          disabled={training}
          className="btn-primary flex items-center gap-2"
        >
          {training && <Loader2 className="animate-spin w-4 h-4" />}
          {training ? 'Entrenando…' : 'Entrenar modelos Ridge + Bootstrap'}
        </button>
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
                    <td className="px-3 py-1.5">{STAT_LABELS[m.stat] ?? m.stat}</td>
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
          <TeamPicker
            season={season} teamId={teamId}
            onSeasonChange={setSeason} onTeamChange={setTeamId}
          />
          <button onClick={handlePredict} disabled={predLoading || !teamId} className="btn-primary">
            {predLoading ? <Loader2 className="animate-spin w-4 h-4" /> : 'Predecir'}
          </button>
        </div>
        {predError && <p className="text-red-400 text-sm">{predError}</p>}

        {pred && (
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm text-slate-200 border-collapse">
              <thead>
                <tr className="bg-slate-700 text-slate-300">
                  <th className="px-3 py-2 text-left">Estadística</th>
                  <th className="px-3 py-2 text-right">Modelo A (estimación)</th>
                  <th className="px-3 py-2 text-right">IC 90% (A)</th>
                  <th className="px-3 py-2 text-right">Modelo B (estimación)</th>
                  <th className="px-3 py-2 text-right">IC 90% (B)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(pred).map(([stat, v]) => (
                  <tr key={stat} className="border-t border-slate-700">
                    <td className="px-3 py-1.5 font-medium">{STAT_LABELS[stat] ?? stat}</td>
                    <td className="px-3 py-1.5 text-right font-semibold text-brand-300">
                      {v.model_a ? fmt(v.model_a.estimate) : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right text-slate-400">
                      {v.model_a ? `[${fmt(v.model_a.ci_low)}, ${fmt(v.model_a.ci_high)}]` : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right font-semibold text-accent-300">
                      {v.model_b ? fmt(v.model_b.estimate) : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right text-slate-400">
                      {v.model_b ? `[${fmt(v.model_b.ci_low)}, ${fmt(v.model_b.ci_high)}]` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
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
          live_team_name:  liveTeam,
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
                {s === 'historical' ? 'Histórico' : 'Temporada actual'}
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
                      {liveTeams.map(t => <option key={t} value={t}>{t}</option>)}
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
                    <th key={s} className="px-3 py-2 text-right">{STAT_LABELS[s] ?? s}</th>
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

// ── Game Prediction tab (FASE 7 — Win/Loss classifier) ────────────────────
function GamePredictionTab() {
  const [seasons, setSeasons]     = useState<string[]>([])
  const [teams, setTeams]         = useState<HistoricalTeamEntry[]>([])
  const [season, setSeason]       = useState('')
  const [teamId, setTeamId]       = useState('')
  const [isHome, setIsHome]       = useState(true)
  const [oppNetRtg, setOppNetRtg] = useState(0)
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

  const run = async () => {
    if (!teamId || !season) return
    setLoading(true); setError(null); setResult(null)
    try {
      const r = await postGamePrediction(teamId, {
        season,
        is_home: isHome,
        opp_net_rtg: oppNetRtg,
      })
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

  // Sort importances descending
  const sortedImportances = result
    ? Object.entries(result.feature_importances).sort(([, a], [, b]) => b - a)
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

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
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
          <input type="number" step="0.5" className={inputCls + ' w-24'}
            value={oppNetRtg}
            onChange={e => setOppNetRtg(parseFloat(e.target.value) || 0)} />
        </div>
        <button
          onClick={run}
          disabled={loading || !teamId}
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

          {/* Feature importances */}
          <div className="bg-slate-800/60 rounded-xl border border-slate-700/50 p-5">
            <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">Importancia de variables</h4>
            <div className="space-y-2">
              {sortedImportances.slice(0, 8).map(([name, val]) => (
                <div key={name}>
                  <div className="flex justify-between text-xs text-slate-400 mb-0.5">
                    <span>{name}</span>
                    <span>{(val * 100).toFixed(1)} %</span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full bg-brand-400"
                      style={{ width: `${val * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Validation tab (FASE 6 — backtesting) ───────────────────────────────────
function ValidationTab() {
  const [seasons, setSeasons]   = useState<string[]>([])
  const [teams, setTeams]       = useState<HistoricalTeamEntry[]>([])
  const [season, setSeason]     = useState('')
  const [teamId, setTeamId]     = useState('')
  const [result, setResult]     = useState<BacktestingResult | null>(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

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

  const run = async () => {
    if (!teamId || !season) return
    setLoading(true); setError(null); setResult(null)
    try {
      const r = await getBacktesting(teamId, season)
      setResult(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const inputCls = 'bg-slate-800 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2 focus:ring-2 focus:ring-brand-500 outline-none'
  const colHdr   = 'text-right text-xs text-slate-400 font-semibold py-2 px-3'
  const cell     = (v: number | null, d = 2) =>
    v == null ? '—' : v.toFixed(d)

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-white mb-1">Validación Walk-Forward</h3>
        <p className="text-xs text-slate-400">
          Evalúa la precisión de los modelos Ridge entrenando sólo con datos pasados
          y midiendo el error en cada partido sucesivo (sin fuga de datos futuros).
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
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
        <button
          onClick={run}
          disabled={loading || !teamId}
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
                <th className={colHdr}>Partidos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/40">
              {Object.entries(result).flatMap(([stat, models]) =>
                (['model_a', 'model_b'] as const).map(mk => {
                  const m = models[mk]
                  return (
                    <tr key={`${stat}-${mk}`} className="hover:bg-slate-800/40">
                      {mk === 'model_a' && (
                        <td rowSpan={2} className="px-3 py-2 font-medium text-slate-300 align-middle border-r border-slate-700/40">
                          {STAT_LABELS[stat] ?? stat}
                        </td>
                      )}
                      <td className="px-3 py-1 text-right text-slate-400 text-xs">
                        {mk === 'model_a' ? 'A (global)' : 'B (cond.)'}
                      </td>
                      <td className="px-3 py-1 text-right tabular-nums">{cell(m.mae)}</td>
                      <td className="px-3 py-1 text-right tabular-nums">{cell(m.rmse)}</td>
                      <td className="px-3 py-1 text-right tabular-nums">
                        {m.mape == null ? '—' : `${m.mape.toFixed(1)} %`}
                      </td>
                      <td className="px-3 py-1 text-right tabular-nums text-slate-400">{m.n_evaluated}</td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {result && Object.keys(result).length === 0 && (
        <p className="text-slate-400 text-sm">
          Sin datos suficientes en HISTORICAL para este equipo y temporada.
        </p>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
type Tab = 'rival' | 'elasticity' | 'montecarlo' | 'prediction' | 'validation'

const TABS: Array<{ id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'rival',       label: 'Ajuste por Rival',   icon: TrendingUp },
  { id: 'elasticity',  label: 'Elasticidades',       icon: BarChart2 },
  { id: 'montecarlo',  label: 'Proyección MC',        icon: Dices },
  { id: 'prediction',  label: 'Predicción Partido',  icon: Target },
  { id: 'validation',  label: 'Validación',           icon: FlaskConical },
]

export default function PredictivePage() {
  const [tab, setTab] = useState<Tab>('rival')

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
          {tab === 'rival'      && <RivalAdjTab />}
          {tab === 'elasticity' && <ElasticityTab />}
          {tab === 'montecarlo' && <MonteCarloTab />}
          {tab === 'prediction' && <GamePredictionTab />}
          {tab === 'validation' && <ValidationTab />}
        </div>
      </div>
    </PageTransition>
  )
}
