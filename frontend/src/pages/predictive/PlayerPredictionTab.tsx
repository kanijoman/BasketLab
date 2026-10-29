/** Predicción Jugador: next-game prediction of a player. */
import { useState } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { useQuery } from '@tanstack/react-query'
import { getPlayerPrediction, getPlayerStats, type PlayerPredictionResult } from '@/api/client'
import Button from '@/components/ui/Button'
import { Field, Input, Select } from '@/components/ui/Field'
import { fmt } from './shared'

// ── FASE 8 — Player Prediction tab ──────────────────────────────────────────
export function PlayerPredictionTab() {
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
      <h2 className="text-lg font-semibold text-ink">Predicción por Jugador</h2>
      <p className="text-ink-muted text-sm">
        Predicción del próximo partido de un jugador usando regresión Ridge sobre su historial
        de la temporada actual en la colección seleccionada.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-wrap gap-4 items-end">
        {/* Team filter */}
        <Field label="Equipo" className="w-48">
          <Select value={teamFilter} onChange={e => handleTeamFilter(e.target.value)}
            options={[{ value: '', label: '— Todos —' }, ...teamNames.map(t => ({ value: t, label: t }))]} />
        </Field>

        {/* Player selector */}
        <Field label="Jugador" className="w-56">
          <Select
            value={playerId}
            onChange={e => {
              const found = filteredPlayers.find(p => p.player_id === e.target.value)
              setPlayerId(e.target.value)
              setPlayerName(found?.player_name ?? '')
            }}
            options={[{ value: '', label: '— Selecciona jugador —' }, ...filteredPlayers.map(p => ({ value: p.player_id, label: p.player_name }))]}
          />
        </Field>

        {/* Home/Away */}
        <Field label="Local / Visitante" className="w-40">
          <Select value={isHome ? 'home' : 'away'} onChange={e => setIsHome(e.target.value === 'home')}
            options={[{ value: 'home', label: 'Local' }, { value: 'away', label: 'Visitante' }]} />
        </Field>

        {/* Opponent net rating */}
        <Field label="Net Rtg rival" className="w-28">
          <Input type="number" value={oppNetRtg} onChange={e => setOppNetRtg(e.target.value)} placeholder="0.0" />
        </Field>

        <Button type="submit" disabled={!playerId} loading={isFetching}>Predecir</Button>
      </form>

      {error && (
        <p className="text-bad text-sm">
          {error instanceof Error ? error.message : 'Error al obtener predicción'}
        </p>
      )}

      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
          {(Object.keys(statLabels) as Array<keyof PlayerPredictionResult>).map(stat => {
            const s = data[stat]
            const hasValue = s.estimate != null
            return (
              <div key={stat} className="bg-surface/60 rounded-lg p-4 space-y-1 border border-line/50">
                <p className="text-xs text-ink-muted uppercase tracking-wider">{statLabels[stat]}</p>
                <p className="text-3xl font-bold text-ink">
                  {hasValue ? fmt(s.estimate) : '—'}
                </p>
                {hasValue && (
                  <p className="text-xs text-ink-muted">
                    IC 90%: {fmt(s.ci_low)} – {fmt(s.ci_high)}
                  </p>
                )}
                <p className="text-xs text-ink-muted">n={s.n_train} partidos</p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
