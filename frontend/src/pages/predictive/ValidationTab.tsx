/** Validación: walk-forward backtesting metrics (Admin > Modelos predictivos). */
import { Field, Select } from '@/components/ui/Field'
import { useState, useEffect } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { getLiveTeamNames, getHistoricalSeasons, getHistoricalTeams, getBacktesting, getBacktestingLive, type HistoricalTeamEntry, type BacktestingResult, type TeamEntry } from '@/api/client'
import { STAT_LABELS } from '@/lib/statLabels'
import Button from '@/components/ui/Button'
import SegmentedControl from '@/components/ui/SegmentedControl'

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

  const colHdr   = 'text-right text-xs text-ink-muted font-semibold py-2 px-3'
  const cell     = (v: number | null | undefined, d = 2) =>
    v == null ? '—' : v.toFixed(d)

  // Stats for which MAPE is suppressed (net_rtg oscillates near zero)
  const MAPE_SUPPRESSED = new Set(['net_rtg'])

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-semibold text-ink mb-1">Validación Walk-Forward</h3>
        <p className="text-xs text-ink-muted">
          Evalúa la precisión de los modelos Ridge entrenando sólo con datos pasados
          y midiendo el error en cada partido sucesivo (sin fuga de datos futuros).
        </p>
      </div>

      {/* Mode toggle */}
      <SegmentedControl label="Temporada del modelo" value={mode} onChange={m => { setMode(m); setResult(null) }}
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
        ) : (
          <Field label={`Equipo — ${collection?.name ?? '…'}`} className="w-64">
            <Select value={liveTeam} onChange={e => setLiveTeam(e.target.value)}>
              {liveTeams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </Field>
        )}
        <Button onClick={run} loading={loading} disabled={mode === 'historical' ? !teamId : !liveTeam}>
          {loading ? 'Calculando…' : 'Ejecutar backtesting'}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg bg-bad/30 border border-bad/50 p-3 text-bad text-sm">{error}</div>
      )}

      {/* Results table */}
      {result && Object.keys(result).length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-line/50">
          <table className="w-full text-sm text-ink border-collapse">
            <thead className="bg-surface/80">
              <tr>
                <th className="text-left text-xs text-ink-muted font-semibold py-2 px-3">Stat</th>
                <th className={colHdr}>Modelo</th>
                <th className={colHdr}>MAE</th>
                <th className={colHdr}>RMSE</th>
                <th className={colHdr}>MAPE %</th>
                <th className={colHdr} title="MAE del modelo dividido entre MAE naive. <1 = modelo mejor que naive">MAE/naive</th>
                <th className={colHdr}>Partidos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/40">
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
                    ? 'text-ink-muted'
                    : ratio < 0.95 ? 'text-ok font-semibold'
                    : ratio > 1.05 ? 'text-bad'
                    : 'text-ink-muted'
                  return (
                    <tr key={`${stat}-${mk}`} className={`hover:bg-surface/40 ${isNaive ? 'bg-surface/20' : ''}`}>
                      {mk === 'model_a' && (
                        <td rowSpan={3} className="px-3 py-2 font-medium text-ink align-middle border-r border-line/40">
                          {STAT_LABELS[stat]?.label ?? stat}
                        </td>
                      )}
                      <td className="px-3 py-1 text-right text-ink-muted text-xs">
                        {mk === 'model_a' ? 'A (global)' : mk === 'model_b' ? 'B (cond.)' : 'Naive (media)'}
                      </td>
                      <td className="px-3 py-1 text-right tabular-nums">{cell(modelMae)}</td>
                      <td className="px-3 py-1 text-right tabular-nums">{cell('rmse' in m ? m.rmse : undefined)}</td>
                      <td className="px-3 py-1 text-right tabular-nums text-ink-muted">
                        {isNaive || !showMape
                          ? '—'
                          : ('mape' in m && m.mape != null ? `${m.mape.toFixed(1)} %` : '—')
                        }
                      </td>
                      <td className={`px-3 py-1 text-right tabular-nums ${ratioCls}`}>
                        {ratio == null ? '—' : ratio.toFixed(2)}
                      </td>
                      <td className="px-3 py-1 text-right tabular-nums text-ink-muted">{m.n_evaluated}</td>
                    </tr>
                  )
                })
                return rows
              })}
            </tbody>
          </table>
          <div className="px-3 py-2 flex gap-4 text-xs text-ink-muted">
            <span><span className="text-ok font-semibold">Verde</span> = modelo mejor que naive (&lt;0.95)</span>
            <span><span className="text-bad">Rojo</span> = naive mejor que modelo (&gt;1.05)</span>
            {Object.keys(result).some(s => MAPE_SUPPRESSED.has(s)) && (
              <span>· MAPE omitido para <span className="font-mono">net_rtg</span> (oscila cerca de cero)</span>
            )}
          </div>
        </div>
      )}

      {result && Object.keys(result).length === 0 && (
        <p className="text-ink-muted text-sm">
          Sin datos suficientes para este equipo y temporada (mínimo {mode === 'live' ? 'temporada actual' : 'HISTORICAL'}).
        </p>
      )}
    </div>
  )
}
