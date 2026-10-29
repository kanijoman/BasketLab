/** Elasticidades: model training and the per-team next-game prediction (Admin > Modelos predictivos). */
import { useState, useEffect } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { useQuery } from '@tanstack/react-query'
import { getElasticityModels, getElasticityPredictLive, getLiveTeamNames, type ElasticityModelMeta, type ElasticityPrediction } from '@/api/client'
import { STAT_LABELS } from '@/lib/statLabels'
import { adminHeaders } from '@/lib/adminKey'
import Button from '@/components/ui/Button'
import SegmentedControl from '@/components/ui/SegmentedControl'
import { Field, Input, Select } from '@/components/ui/Field'
import { Waiting } from './shared'
import { fmt } from './shared'

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
        headers: { 'Content-Type': 'application/json', ...adminHeaders() },
        body: JSON.stringify({}),
      })
      if (res.status === 401 || res.status === 503) {
        const b = await res.json().catch(() => ({}))
        throw new Error(b.detail ?? 'Se requiere la clave de administración (pestaña Admin)')
      }
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
      <div className="bg-surface/50 rounded-lg p-4 space-y-3">
        <h3 className="font-semibold text-ink">Entrenar modelos de elasticidad</h3>
        <p className="text-sm text-ink-muted">
          Entrena cuatro modelos con datos de HISTORICAL:{' '}
          <span className="text-ink font-medium">Modelo A</span> (rolling global),{' '}
          <span className="text-ink font-medium">Modelo B</span> (+ local/visitante y rival),{' '}
          <span className="text-ink font-medium">Modelo C</span> (+ ventana larga, momentum y cross-stats) y{' '}
          <span className="text-ink font-medium">Modelo D</span> (GBM con intervalos cuantílicos).
          Requiere haber ejecutado la ingesta histórica previamente.
        </p>
        <Button onClick={handleTrain} loading={training}>
          {training ? 'Entrenando…' : 'Entrenar modelos (Ridge A/B/C + GBM D)'}
        </Button>

        {/* Live progress */}
        {training && (
          <div className="space-y-1.5">
            <div className="w-full bg-surface-raised rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-accent-solid h-1.5 rounded-full transition-all duration-300"
                style={{ width: trainProgress ? `${(trainProgress.current / trainProgress.total) * 100}%` : '0%' }}
              />
            </div>
            <p className="text-xs text-ink-muted font-mono">
              {trainProgress ? trainProgress.step : 'Iniciando entrenamiento…'}
            </p>
          </div>
        )}

        {trainMsg && <p className="text-sm text-accent-text">{trainMsg}</p>}
      </div>

      {/* Models list */}
      {models.length > 0 && (
        <div>
          <h3 className="font-semibold text-ink mb-2">Modelos almacenados</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-ink border-collapse">
              <thead>
                <tr className="bg-surface-raised text-ink">
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
                  <tr key={`${m.model_type}-${m.stat}`} className="border-t border-line">
                    <td className="px-3 py-1.5 font-mono text-accent-text">Modelo {m.model_type}</td>
                    <td className="px-3 py-1.5">{STAT_LABELS[m.stat]?.label ?? m.stat}</td>
                    <td className="px-3 py-1.5 text-ink-muted">{m.league}</td>
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
      <div className="bg-surface/50 rounded-lg p-4 space-y-3">
        <h3 className="font-semibold text-ink">Predecir próximo partido</h3>

        <div className="flex gap-3 flex-wrap items-end">
          {loadingLiveTeams || !collection || liveTeams.length === 0 ? (
            <Waiting label="Equipo" loading={loadingLiveTeams}
              empty={!collection ? 'Selecciona una colección primero' : 'Sin equipos en esta colección'} />
          ) : (
            <Field label="Equipo (temporada actual)" className="w-56">
              <Select value={liveTeam} onChange={e => setLiveTeam(e.target.value)}
                options={[{ value: '', label: 'Seleccionar equipo…' }, ...liveTeams.map(t => ({ value: t.id, label: t.name }))]} />
            </Field>
          )}
          <Button onClick={handlePredict} loading={predLoading} disabled={!canPredict}>Predecir</Button>
        </div>

        {/* Optional Modelo B inputs */}
        <div className="flex gap-4 flex-wrap items-end pt-1">
          <div className="space-y-1">
            <span className="block text-xs font-medium text-ink-muted">
              ¿Local o visitante? <span className="text-ink-muted">(opcional — activa Modelo B)</span>
            </span>
            <SegmentedControl label="Local o visitante" value={isHome === null ? 'any' : isHome ? 'home' : 'away'}
              onChange={v => setIsHome(v === 'any' ? null : v === 'home')}
              options={[{ value: 'any', label: 'Sin especificar' }, { value: 'home', label: 'Local' }, { value: 'away', label: 'Visitante' }]} />
          </div>
          <Field label="Net Rating rival (opcional)" className="w-44">
            <Input type="number" step="0.1" placeholder="p.ej. -2.5" value={oppNetRtg} onChange={e => setOppNetRtg(e.target.value)} />
          </Field>
        </div>
        {predError && <p className="text-bad text-sm">{predError}</p>}

        {pred && (() => {
          const hasModelB = Object.values(pred).some(v => v.model_b)
          return (
          <div className="overflow-x-auto mt-3">
            <table className="w-full text-sm text-ink border-collapse">
              <thead>
                <tr className="bg-surface-raised text-ink">
                  <th className="px-3 py-2 text-left">Estadística</th>
                  <th className="px-3 py-2 text-right">Modelo A (estimación)</th>
                  <th className="px-3 py-2 text-right">IC 90% (A)</th>
                  {hasModelB && <th className="px-3 py-2 text-right">Modelo B (estimación)</th>}
                  {hasModelB && <th className="px-3 py-2 text-right">IC 90% (B)</th>}
                </tr>
              </thead>
              <tbody>
                {Object.entries(pred).map(([stat, v]) => (
                  <tr key={stat} className="border-t border-line">
                    <td className="px-3 py-1.5 font-medium">{STAT_LABELS[stat]?.label ?? stat}</td>
                    <td className="px-3 py-1.5 text-right font-semibold text-accent-text">
                      {v.model_a ? fmt(v.model_a.estimate) : '—'}
                    </td>
                    <td className="px-3 py-1.5 text-right text-ink-muted">
                      {v.model_a ? `[${fmt(v.model_a.ci_low)}, ${fmt(v.model_a.ci_high)}]` : '—'}
                    </td>
                    {hasModelB && (
                      <td className="px-3 py-1.5 text-right font-semibold text-secondary-text">
                        {v.model_b ? fmt(v.model_b.estimate) : '—'}
                      </td>
                    )}
                    {hasModelB && (
                      <td className="px-3 py-1.5 text-right text-ink-muted">
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
