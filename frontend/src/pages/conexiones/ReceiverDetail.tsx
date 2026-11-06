/** The detail of one player: how much of his scoring comes from assists, who feeds him, where he scores with and without an assist and, as a passer, who he finds (issue #773). */
import type { Passer, Receiver } from '@/api/assistConnections'
import AssistZoneCourt from '@/components/AssistZoneCourt'
import { pct, plural } from './format'

function Figure({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="card p-3">
      <p className="text-xs font-medium text-ink-muted uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-ink leading-none mt-1">{value}</p>
      <p className="text-xs text-ink-faint mt-1">{hint}</p>
    </div>
  )
}

interface Props {
  name: string
  receiver: Receiver | null
  passer: Passer | null
}

export default function ReceiverDetail({ name, receiver, passer }: Props) {
  const feeders = receiver?.from ?? []
  const biggest = Math.max(1, ...feeders.map(f => f.count))
  return (
    <section aria-label={`Detalle de ${name}`} className="card p-4 space-y-4">
      <h2 className="text-lg font-semibold text-ink">{name}</h2>
      {receiver ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Figure label="Canastas asistidas" value={pct(receiver.assisted_pct)} hint={`${receiver.received} de ${receiver.fgm} canastas de campo`} />
            <Figure label="Puntos asistidos" value={pct(receiver.assisted_points_pct)} hint={`${receiver.assisted_points} de ${receiver.points} puntos de campo`} />
            <Figure label="Canastas creadas por él" value={String(receiver.unassisted)} hint="anotadas sin que nadie le asista" />
          </div>
          {receiver.received === 0 && <p className="text-sm text-ink-muted">{name} no ha anotado con asistencia: todo lo que ha metido se lo ha creado él.</p>}
          {feeders.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-ink">Quién le surte de balones</h3>
              <ul className="space-y-1">
                {feeders.map(f => (
                  <li key={f.player_id} className="flex items-center gap-2 text-sm">
                    <span className="w-40 truncate text-ink">{f.name}</span>
                    <span aria-hidden className="h-2 rounded bg-accent" style={{ width: `${(100 * f.count) / biggest}%`, maxWidth: '40%' }} />
                    <span className="text-ink-muted">{f.count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-ink">Desde dónde anota: con asistencia y sin ella</h3>
            <AssistZoneCourt zones={receiver.zones} withoutZone={receiver.without_zone} />
          </div>
        </>
      ) : (
        <p className="text-sm text-ink-muted">{name} no figura entre los anotadores de este equipo.</p>
      )}
      {passer && (
        <p className="text-sm text-ink">
          Como pasador {name} da {plural(passer.assists, 'asistencia', 'asistencias')}: {passer.to.map(t => `${t.name} (${t.count})`).join(', ')}.
        </p>
      )}
    </section>
  )
}
