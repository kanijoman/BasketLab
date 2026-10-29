/** Proyección MC: Monte Carlo simulation of N future games of a team. */
import { useState } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { useQuery } from '@tanstack/react-query'
import { postMonteCarlo, getLiveTeamNames, type MonteCarloResult, type TeamEntry } from '@/api/client'
import { STAT_LABELS } from '@/lib/statLabels'
import { Dices } from 'lucide-react'
import Button from '@/components/ui/Button'
import SegmentedControl from '@/components/ui/SegmentedControl'
import { Field, Input, Select } from '@/components/ui/Field'
import { fmt, pct, TeamPicker, Waiting } from './shared'

// ── Monte Carlo tab ───────────────────────────────────────────────────────────
export type MCSource = 'historical' | 'live'

export function MonteCarloTab() {
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
      <div className="bg-surface/50 rounded-lg p-4 space-y-4">
        <h3 className="font-semibold text-ink">Configurar simulación</h3>

        {/* Source toggle */}
        <div className="space-y-1">
          <SegmentedControl label="Fuente de datos" size="md" value={source} onChange={handleSourceChange}
            options={[{ value: 'historical', label: 'Temporadas anteriores' }, { value: 'live', label: 'Temporada actual' }]} />
          {source === 'live' && (
            <p className="text-xs text-ink-muted mt-1">
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
          ) : loadingLiveTeams || liveTeams.length === 0 ? (
            <Waiting label="Equipo" loading={loadingLiveTeams} empty="Sin equipos en esta colección" />
          ) : (
            <Field label="Equipo (temporada actual)" className="w-56">
              <Select value={liveTeam} onChange={e => setLiveTeam(e.target.value)}
                options={[{ value: '', label: 'Seleccionar equipo…' }, ...liveTeams.map((t: TeamEntry) => ({ value: t.id, label: t.name }))]} />
            </Field>
          )}

          <Field label="Partidos a proyectar" className="w-24">
            <Input type="number" min={1} max={10} value={nGames} onChange={e => setNGames(Number(e.target.value))} />
          </Field>
          <Field label="Simulaciones" className="w-28">
            <Select value={nSims} onChange={e => setNSims(Number(e.target.value))}
              options={[100, 500, 1000, 2000, 5000].map(n => ({ value: String(n), label: n.toLocaleString() }))} />
          </Field>
          <Button icon={Dices} loading={loading} onClick={handleSimulate} disabled={!canSimulate}>
            {loading ? 'Simulando…' : 'Simular'}
          </Button>
        </div>
        {error && <p className="text-bad text-sm">{error}</p>}
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
              <div key={label} className="bg-surface rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-accent-text">{value}</p>
                <p className="text-xs text-ink-muted mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* Per-game table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-ink border-collapse">
              <thead>
                <tr className="bg-surface-raised text-ink">
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
                  <tr key={g.game_index} className="border-t border-line">
                    <td className="px-3 py-1.5 text-center font-medium">#{g.game_index}</td>
                    <td className="px-3 py-1.5 text-center text-ink-muted">
                      {g.is_home === null ? '—' : g.is_home ? 'Local' : 'Visitante'}
                    </td>
                    <td className={`px-3 py-1.5 text-right font-semibold ${
                      g.win_prob >= 0.5 ? 'text-ok' : 'text-bad'
                    }`}>
                      {pct(g.win_prob)}
                    </td>
                    {Object.entries(g.stats).map(([s, sv]) => (
                      <td key={s} className="px-3 py-1.5 text-right">
                        <span className="font-medium">{fmt(sv.mean)}</span>
                        <span className="text-ink-muted text-xs ml-1">
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
