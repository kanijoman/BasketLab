/** The passer's side of a player (issue #773): who he passes to and from where those players score. Choosing one of them narrows the court to the assists to him. */
import { useState } from 'react'
import type { Passer } from '@/api/assistConnections'
import PassZoneCourt from '@/components/PassZoneCourt'
import Button from '@/components/ui/Button'
import { pct, plural } from './format'

export default function PasserSection({ passer }: { passer: Passer }) {
  const [targetId, setTargetId] = useState<string | null>(null)
  const target = passer.to.find(t => t.player_id === targetId) ?? null
  // a publication from before the zones of the passers existed has neither `zones` nor `without_zone`: the passes show and the court says its data is on the way
  const published = (target ?? passer).zones !== undefined
  const zones = (target ?? passer).zones ?? []
  const withoutZone = (target ?? passer).without_zone ?? 0
  return (
    <section aria-label="Como pasador" className="space-y-3 border-t border-line pt-4">
      <h3 className="text-sm font-semibold text-ink">
        Como pasador: da {plural(passer.assists, 'asistencia', 'asistencias')} ({pct(passer.share_pct)} de las del equipo)
      </h3>
      <div className="space-y-1">
        <p className="text-xs text-ink-muted">A quién le pasa: elige un jugador para ver solo desde dónde anota con sus pases.</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={target ? 'secondary' : 'primary'} aria-pressed={!target} onClick={() => setTargetId(null)}>Todos</Button>
          {passer.to.map(t => (
            <Button key={t.player_id} size="sm" variant={t.player_id === targetId ? 'primary' : 'secondary'} aria-pressed={t.player_id === targetId} onClick={() => setTargetId(t.player_id)}>
              <span>{t.name}</span> <span className="opacity-80">{t.count}</span>
            </Button>
          ))}
        </div>
      </div>
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-ink">{target ? `Desde dónde anota ${target.name} con sus pases` : 'Desde dónde anotan los jugadores a los que asiste'}</h4>
        {published
          ? <PassZoneCourt zones={zones} withoutZone={withoutZone} />
          : <p className="text-sm text-ink-muted py-4">Todavía no están publicadas las zonas de los pases de esta competición: aparecerán con la próxima publicación de datos.</p>}
      </div>
    </section>
  )
}
