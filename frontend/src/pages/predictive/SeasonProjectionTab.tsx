/** Clasificación Final: projection of the end of the season. */
import { useState } from 'react'
import { useCollection } from '@/context/CollectionContext'
import { useQuery } from '@tanstack/react-query'
import { getSeasonProjection, type SeasonProjectionEntry } from '@/api/client'
import Button from '@/components/ui/Button'
import { Field, Input } from '@/components/ui/Field'
import { fmt, pct } from './shared'

// ── FASE 9 — Season Projection tab ──────────────────────────────────────────
export function SeasonProjectionTab() {
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
      <h2 className="text-lg font-semibold text-ink">Proyección de Clasificación Final</h2>
      <p className="text-ink-muted text-sm">
        Proyección Monte Carlo de la clasificación final de la liga simulando los partidos
        restantes usando modelos de net rating. Muestra victorias proyectadas, probabilidad
        de playoff y distribución de posiciones para cada equipo.
      </p>

      {!collectionName && (
        <p className="text-ink-muted text-sm italic">Selecciona una colección primero.</p>
      )}

      {collectionName && (
        <form onSubmit={handleSubmit} className="flex flex-wrap gap-4 items-end">
          <Field label="Partidos/temporada" className="w-28">
            <Input type="number" value={seasonLength} onChange={e => setSeasonLength(Number(e.target.value))} min={1} max={40} />
          </Field>

          <Button type="submit" loading={isFetching}>Proyectar</Button>
        </form>
      )}

      {error && (
        <p className="text-bad text-sm">
          {error instanceof Error ? error.message : 'Error al obtener proyección'}
        </p>
      )}

      {data && data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-ink border-collapse">
            <thead>
              <tr className="text-ink-muted border-b border-line">
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
                <tr key={entry.team_id} className="border-b border-line hover:bg-surface/30">
                  <td className="py-2 px-3 text-ink-muted">{idx + 1}</td>
                  <td className="py-2 px-3 font-medium">{entry.team_name}</td>
                  <td className="py-2 px-3 text-right">
                    {entry.wins_so_far}-{entry.losses_so_far}
                  </td>
                  <td className="py-2 px-3 text-right font-semibold">
                    {fmt(entry.proj_wins)}
                  </td>
                  <td className="py-2 px-3 text-right text-ink-muted text-xs">
                    {fmt(entry.proj_wins_ci_low)}–{fmt(entry.proj_wins_ci_high)}
                  </td>
                  <td className={`py-2 px-3 text-right font-semibold ${
                    entry.playoff_prob >= 0.7 ? 'text-ok' :
                    entry.playoff_prob >= 0.4 ? 'text-warn' : 'text-bad'
                  }`}>
                    {pct(entry.playoff_prob)}
                  </td>
                  <td className="py-2 px-3 text-right text-ink">
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
