// The players like him in the profile (#1010): the five whose percentiles are closest to his, in his own competition and season. `SimilarList` draws a result (and says why there is none);
// `SimilarPlayers` finds it: it opens the file of the competition of the row (the same key and cache as the search and the rest of the profile). The rules are in `similar.ts`.
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import Card from '@/components/ui/Card'
import Spinner from '@/components/ui/Spinner'
import { loadCompetitionRows, loadTalentCompetitions } from './data'
import { ENOUGH_MINUTES } from './enoughMinutes'
import { toSearchRow, type SearchRow } from './search'
import { similarPlayers, type SimilarResult } from './similar'

const REASON = {
  'few-minutes': `Sin parecidos: este jugador no tiene minutos suficientes en esta competición (${ENOUGH_MINUTES}) y su perfil sería orientativo.`,
  'no-profile': 'Sin parecidos: este jugador está sin perfil en esta competición.',
} as const

export default function SimilarList({ result, targetId, loading }: { result: SimilarResult; targetId: string; loading: boolean }) {
  return (
    <Card title="Jugadores parecidos">
      {loading && <Spinner size="sm" label="Buscando jugadores parecidos" />}
      {!loading && result.reason && <p className="text-sm text-ink-muted">{REASON[result.reason]}</p>}
      {!loading && !result.reason && result.similar.length === 0 && <p className="text-sm text-ink-muted">Ningún jugador de la competición tiene un perfil comparable (hace falta que compartan al menos seis de los ocho ejes).</p>}
      {!loading && result.similar.length > 0 && (
        <ul aria-label="Jugadores parecidos" className="divide-y divide-line/60">
          {result.similar.map(s => {
            const name = s.row.full_name ?? s.row.name
            return (
              <li key={s.row.person_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
                <div className="min-w-0 flex-1">
                  <Link to={`/jugador/${encodeURIComponent(s.row.person_id)}`} className="font-medium text-accent-text hover:underline">{name}</Link>
                  <p className="text-xs text-ink-muted">{s.row.team_name} · {s.row.age === null ? <span title="Sin dato" className="text-ink-faint">—</span> : `${s.row.age} años`}</p>
                </div>
                <span className="text-sm font-semibold tabular-nums text-ink" title={`Parecido en ${s.axes} de los 8 ejes`}>{Math.round(s.similarity)} %</span>
                <Link to={`/comparar?j=${encodeURIComponent(`${targetId},${s.row.person_id}`)}`} aria-label={`Comparar con ${name}`} className="text-xs font-medium text-accent-text hover:underline">Comparar</Link>
              </li>
            )
          })}
        </ul>
      )}
      <p className="mt-3 text-xs text-ink-muted">
        Solo se comparan jugadores de la misma competición y temporada que han jugado lo suficiente. El parecido es 100 menos la diferencia media, en puntos de percentil, en los ejes del radar que ambos tienen; no mira la posición, la altura ni la edad (la edad se ve junto a cada uno).
      </p>
    </Card>
  )
}

export function SimilarPlayers({ row, targetId }: { row: SearchRow; targetId: string }) {
  const manifest = useQuery({ queryKey: ['talent-competitions'], queryFn: loadTalentCompetitions })
  const entry = manifest.data?.find(e => e.key === row.comp_key)
  const rows = useQuery({ queryKey: ['talent-rows', row.comp_key], queryFn: () => loadCompetitionRows(row.comp_key), enabled: Boolean(entry) })
  const result = useMemo(() => (rows.data && entry ? similarPlayers(rows.data.rows.map(r => toSearchRow(entry, r)), row) : { similar: [], reason: null } as SimilarResult), [rows.data, entry, row])
  return <SimilarList result={result} targetId={targetId} loading={manifest.isLoading || rows.isLoading} />
}
