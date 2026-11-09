/** From where the players a passer finds score, on one court (issue #773, the passer's side).
 *  One bubble per zone (`ZoneBubbleCourt`): its size is the number of assists that end there; the ring and the small figure are its share of all his assists (those with no known zone count in the total). */
import type { PassZone } from '@/api/assistConnections'
import ZoneBubbleCourt, { type ZoneBubble } from '@/components/ZoneBubbleCourt'
import { ZONE_CENTERS } from '@/components/ui/FibaCourtSVG'

interface Props {
  zones: PassZone[]
  /** Assists whose basket has no known zone (no shot coordinates): in the total of the percentages and said under the court. */
  withoutZone?: number
}

export default function PassZoneCourt({ zones, withoutZone = 0 }: Props) {
  const drawn = zones.filter(z => z.count > 0 && ZONE_CENTERS[z.zone])
  const total = drawn.reduce((sum, z) => sum + z.count, 0) + withoutZone
  const bubbles: ZoneBubble[] = drawn.map(z => ({
    zone: z.zone, total: z.count, share: z.count / total, percent: Math.round((100 * z.count) / total),
    title: `${ZONE_CENTERS[z.zone].label}: ${z.count} ${z.count === 1 ? 'asistencia acaba' : 'asistencias acaban'} en canasta desde aquí`,
  }))
  return (
    <ZoneBubbleCourt bubbles={bubbles} marker="data-pass-zone" empty="Sin asistencias con zona conocida para este jugador.">
      <span>Tamaño: asistencias que acaban en canasta desde la zona · anillo y cifra pequeña: % de sus asistencias</span>
      {withoutZone > 0 && <span>{withoutZone} {withoutZone === 1 ? 'asistencia sin zona' : 'asistencias sin zona'} no salen en la pista</span>}
    </ZoneBubbleCourt>
  )
}
