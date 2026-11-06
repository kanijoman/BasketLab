/** Conexiones de asistencia (issue #773): who passes, who receives and from which zones the receiver scores, assisted against not assisted. FEB and FBCYL. */
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAssistConnections, type AssistConnections } from '@/api/assistConnections'
import { getTeamStats } from '@/api/client'
import { useCollection } from '@/context/CollectionContext'
import PageTransition from '@/components/ui/PageTransition'
import PageHeader from '@/components/ui/PageHeader'
import Spinner from '@/components/ui/Spinner'
import { Select } from '@/components/ui/Field'
import PassersTable from './conexiones/PassersTable'
import ReceiverDetail from './conexiones/ReceiverDetail'
import ReceiverTable from './conexiones/ReceiverTable'
import { pct } from './conexiones/format'

/** Every player of the team that appears in the analysis, as scorer or as passer, by name. */
function people(data: AssistConnections): { id: string; name: string }[] {
  const byId = new Map<string, string>()
  data.receivers.forEach(r => byId.set(r.player_id, r.name))
  data.passers.forEach(p => byId.set(p.player_id, p.name))
  return [...byId.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name))
}

export default function ConexionesPage() {
  const { collection } = useCollection()
  const [teamId, setTeamId] = useState<string | null>(null)
  const [playerId, setPlayerId] = useState<string | null>(null)

  const { data: teamData } = useQuery({
    queryKey: ['team-list-conexiones', collection?.name],
    queryFn: () => getTeamStats(collection!.name),
    enabled: Boolean(collection),
    staleTime: 10 * 60_000,
  })
  const teams = useMemo(
    () => (teamData?.team_stats ?? []).map(t => ({ name: t.team_name, id: String(t.team_id ?? t.team_name) })).sort((a, b) => a.name.localeCompare(b.name)),
    [teamData],
  )
  useEffect(() => { if (teamId === null && teams.length > 0) setTeamId(teams[0].id) }, [teams, teamId])
  useEffect(() => setPlayerId(null), [teamId, collection?.name])

  const { data, error, isFetching } = useQuery({
    queryKey: ['assist-connections', collection?.name, teamId],
    queryFn: () => getAssistConnections(collection!.name, teamId!),
    enabled: Boolean(collection) && teamId !== null,
    staleTime: 10 * 60_000,
    retry: false,
  })

  const selected = useMemo(() => {
    if (!data || playerId === null) return null
    const receiver = data.receivers.find(r => r.player_id === playerId) ?? null
    const passer = data.passers.find(p => p.player_id === playerId) ?? null
    const name = receiver?.name ?? passer?.name ?? playerId
    return { name, receiver, passer }
  }, [data, playerId])

  return (
    <PageTransition>
      <div className="space-y-4">
        <PageHeader title="Conexiones de asistencia" subtitle={collection?.label} />

        <div className="card p-4 flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1">Equipo</label>
            <Select aria-label="Equipo" value={teamId ?? ''} onChange={e => setTeamId(e.target.value)}>
              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-muted mb-1">Jugador</label>
            <Select aria-label="Jugador" value={playerId ?? ''} onChange={e => setPlayerId(e.target.value || null)} disabled={!data}>
              <option value="">Todos</option>
              {(data ? people(data) : []).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </Select>
          </div>
        </div>

        {collection?.isFbcyl && (
          <p className="text-sm text-ink-muted">El play-by-play de FBCYL está anotado por los clubes y puede tener errores: las conexiones son orientativas.</p>
        )}
        {error && <p role="alert" className="text-bad text-sm bg-bad/10 border border-bad/30 rounded-lg p-3">{error instanceof Error ? error.message : String(error)}</p>}
        {isFetching && !data && <Spinner />}

        {data && data.total_baskets === 0 && <p className="text-sm text-ink-muted">Sin canastas registradas para este equipo en esta competición.</p>}
        {data && data.total_baskets > 0 && (
          <>
            <p className="text-xs text-ink-muted">
              {data.games} partidos · {data.assists_linked} de {data.assists_total} asistencias ({pct(data.linked_pct)}) se han podido enlazar a una canasta; las demás no se
              cuentan. Solo se estudian canastas de campo: un pase que acaba en fallo no se puede enlazar, así que no hay porcentaje de acierto.
            </p>
            <section aria-label="Receptores" className="space-y-2">
              <h2 className="text-lg font-semibold text-ink">Receptores</h2>
              <p className="text-xs text-ink-muted">Todos los jugadores que han anotado; pulsa una columna para ordenar y un jugador para ver su detalle.</p>
              <ReceiverTable receivers={data.receivers} selectedId={playerId} onSelect={setPlayerId} />
            </section>
            {selected
              ? <ReceiverDetail name={selected.name} receiver={selected.receiver} passer={selected.passer} />
              : <p className="text-sm text-ink-muted">Elige un jugador (en la tabla o en el filtro) para ver cuánto anota con asistencia, quién le surte y desde dónde.</p>}
            <PassersTable passers={data.passers} onSelect={setPlayerId} />
          </>
        )}
      </div>
    </PageTransition>
  )
}
