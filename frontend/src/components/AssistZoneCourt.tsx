/** The zones a player scores from, assisted against not assisted, on one court (issue #773).
 *  One bubble per zone (`ZoneBubbleCourt`): its size is the number of baskets there; the ring is split in two colours, the share with an assist and the rest. Labels inside say the baskets and the % assisted. */
import type { ConnectionZone } from '@/api/assistConnections'
import ZoneBubbleCourt, { type ZoneBubble } from '@/components/ZoneBubbleCourt'
import { useChartTheme } from '@/lib/chartTheme'
import { ZONE_CENTERS } from '@/components/ui/FibaCourtSVG'

interface Props {
  zones: ConnectionZone[]
  /** Baskets of the player whose zone is unknown (no shot coordinates): said under the court. */
  withoutZone?: number
}

export default function AssistZoneCourt({ zones, withoutZone = 0 }: Props) {
  const chart = useChartTheme()
  const bubbles: ZoneBubble[] = zones.filter(z => ZONE_CENTERS[z.zone]).map(z => {
    const total = z.assisted + z.unassisted
    return { zone: z.zone, total, share: total ? z.assisted / total : 0, percent: Math.round(z.assisted_pct ?? 0),
      title: `${ZONE_CENTERS[z.zone].label}: ${total} canastas, ${z.assisted} con asistencia y ${z.unassisted} sin asistencia` }
  })
  return (
    <ZoneBubbleCourt bubbles={bubbles} marker="data-zone" empty="Sin canastas con zona conocida para este jugador.">
      <span className="flex items-center gap-1"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chart.series[0] }} />Con asistencia</span>
      <span className="flex items-center gap-1"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: chart.faint, opacity: 0.55 }} />Sin asistencia</span>
      <span>Tamaño: canastas en la zona · cifra pequeña: % con asistencia</span>
      {withoutZone > 0 && <span>{withoutZone} {withoutZone === 1 ? 'canasta sin zona' : 'canastas sin zona'} no salen en la pista</span>}
    </ZoneBubbleCourt>
  )
}
