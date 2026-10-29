/** Predicción Partido: win probability of the next game. */
import { Field, Input, Select } from '@/components/ui/Field'
import { useState, useEffect } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, getHistoricalSeasons, getHistoricalTeams, postGamePrediction, type HistoricalTeamEntry, type GamePredictionResult, type TeamEntry } from '@/api/client'
import Button from '@/components/ui/Button'
import SegmentedControl from '@/components/ui/SegmentedControl'

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
export function GamePredictionTab() {
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

  const probColor = (p: number) =>
    p >= 0.6 ? 'text-ok' : p <= 0.4 ? 'text-bad' : 'text-warn'

  const sortedImportances = result
    ? Object.entries(result.feature_importances).sort(([, a], [, b]) => b - a).slice(0, 9)
    : []

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-ink mb-1">Predicción Victoria/Derrota</h3>
        <p className="text-xs text-ink-muted">
          Regresión Logística calibrada entrenada sobre el historial de la temporada.
          Usa rolling-window de Net Rtg, eFG% y TOV% más contexto local/visitante y fuerza del rival.
        </p>
      </div>

      {/* Mode toggle */}
      <SegmentedControl label="Temporada del modelo" value={mode}
        onChange={m => { setMode(m); setResult(null); setError(null) }}
        options={[{ value: 'historical', label: 'Temporada histórica' }, { value: 'live', label: 'Temporada actual' }]} />

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end">
        {mode === 'historical' ? (
          <>
            <Field label="Temporada" className="w-40">
              <Select value={season} onChange={e => setSeason(e.target.value)}>
                {seasons.map(s => <option key={s} value={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Equipo" className="w-56">
              <Select value={teamId} onChange={e => setTeamId(e.target.value)}>
                {teams.map(t => <option key={t.team_id} value={t.team_id}>{t.team_name}</option>)}
              </Select>
            </Field>
          </>
        ) : collection ? (
          <Field label="Equipo (temporada actual)" className="w-64">
            <Select value={liveTeam} onChange={e => setLiveTeam(e.target.value)}>
              {(liveTeams as TeamEntry[]).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </Field>
        ) : (
          <p className="text-xs text-ink-muted italic">Selecciona una colección primero</p>
        )}

        <Field label="Campo" className="w-36">
          <Select value={isHome ? 'home' : 'away'} onChange={e => setIsHome(e.target.value === 'home')}
            options={[{ value: 'home', label: 'Local' }, { value: 'away', label: 'Visitante' }]} />
        </Field>
        <Field label="Net Rtg rival" className="w-28">
          <Input type="number" placeholder="0.0" value={oppNetRtg} onChange={e => setOppNetRtg(e.target.value)} />
        </Field>
        <Button onClick={run} loading={loading} disabled={mode === 'historical' ? !teamId : !liveTeam}>
          {loading ? 'Calculando…' : 'Predecir'}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg bg-bad/30 border border-bad/50 p-3 text-bad text-sm">{error}</div>
      )}

      {result && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Probability card */}
          <div className="bg-surface/60 rounded-xl border border-line/50 p-5 flex flex-col items-center gap-3">
            <span className="text-xs text-ink-muted uppercase tracking-wider">P(Victoria)</span>
            <span className={`text-5xl font-bold tabular-nums ${probColor(result.win_prob)}`}>
              {(result.win_prob * 100).toFixed(1)}&thinsp;%
            </span>
            <span className="text-xs text-ink-muted">
              IC 90 %: {(result.ci_low * 100).toFixed(1)} % – {(result.ci_high * 100).toFixed(1)} %
            </span>
            <div className="w-full bg-surface-raised rounded-full h-2 mt-1">
              <div
                className="h-2 rounded-full bg-accent-solid transition-all"
                style={{ width: `${result.win_prob * 100}%` }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3 w-full text-center mt-1">
              <div>
                <p className="text-xs text-ink-muted">Partidos entrenados</p>
                <p className="text-sm font-semibold text-ink">{result.n_train}</p>
              </div>
              <div>
                <p className="text-xs text-ink-muted">Accuracy walk-fwd</p>
                <p className="text-sm font-semibold text-ink">
                  {result.accuracy != null ? `${(result.accuracy * 100).toFixed(1)} %` : '—'}
                </p>
              </div>
            </div>
          </div>

          {/* Feature importances with sign */}
          <div className="bg-surface/60 rounded-xl border border-line/50 p-5">
            <h4 className="text-xs font-semibold text-ink uppercase tracking-wider mb-1">
              Importancia de variables
            </h4>
            <p className="text-xs text-ink-muted mb-3">
              <span className="text-ok">Verde</span> = favorece la victoria · 
              <span className="text-bad">Rojo</span> = la perjudica
            </p>
            <div className="space-y-2.5">
              {sortedImportances.map(([name, absVal]) => {
                const coef = result.feature_coefficients?.[name] ?? absVal
                const positive = coef >= 0
                const barColor = positive ? 'bg-ok' : 'bg-bad'
                const label = FEAT_LABELS[name] ?? name
                return (
                  <div key={name}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-ink">{label}</span>
                      <span className={positive ? 'text-ok' : 'text-bad'}>
                        {positive ? '+' : '−'}{(absVal * 100).toFixed(1)} %
                      </span>
                    </div>
                    <div className="w-full bg-surface-raised rounded-full h-1.5">
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
