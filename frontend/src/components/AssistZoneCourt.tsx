/** The zones a player scores from, assisted against not assisted, on one court (issue #773).
 *  One bubble per zone: its size is the number of baskets there; the ring is split in two colours, the share with an assist and the rest. Labels inside say the baskets and the % assisted. */
import type { ConnectionZone } from '@/api/assistConnections'
import FibaCourtSVG, { ZONE_CENTERS } from '@/components/ui/FibaCourtSVG'
import { useChartTheme } from '@/lib/chartTheme'

const RING = 7

/** The assisted arc of a ring of radius `r` centred on (cx, cy), from the top, clockwise. */
function arc(cx: number, cy: number, r: number, share: number): string {
  const angle = share * 2 * Math.PI
  const x = cx + r * Math.sin(angle)
  const y = cy - r * Math.cos(angle)
  return `M ${cx} ${cy - r} A ${r} ${r} 0 ${share > 0.5 ? 1 : 0} 1 ${x} ${y}`
}

interface Props {
  zones: ConnectionZone[]
  /** Baskets of the player whose zone is unknown (no shot coordinates): said under the court. */
  withoutZone?: number
}

export default function AssistZoneCourt({ zones, withoutZone = 0 }: Props) {
  const chart = useChartTheme()
  const drawn = zones.filter(z => z.assisted + z.unassisted > 0 && ZONE_CENTERS[z.zone])
  const max = Math.max(1, ...drawn.map(z => z.assisted + z.unassisted))
  const assistedColour = chart.series[0]
  const restColour = chart.faint
  return (
    <figure className="flex flex-col items-center gap-2">
      {drawn.length === 0 ? (
        <p className="text-sm text-ink-muted py-8">Sin canastas con zona conocida para este jugador.</p>
      ) : (
        <FibaCourtSVG vizMode="scatter">
          {drawn.map(z => {
            const c = ZONE_CENTERS[z.zone]
            const total = z.assisted + z.unassisted
            const r = 17 + 13 * Math.sqrt(total / max)
            const share = z.assisted / total
            return (
              <g key={z.zone} data-zone={z.zone}>
                <title>{`${c.label}: ${total} canastas, ${z.assisted} con asistencia y ${z.unassisted} sin asistencia`}</title>
                <circle cx={c.x} cy={c.y} r={r} fill={chart.floor} />
                <circle cx={c.x} cy={c.y} r={r} fill="none" stroke={share === 1 ? assistedColour : restColour} strokeWidth={RING} strokeOpacity={share === 1 ? 1 : 0.55} />
                {share > 0 && share < 1 && <path d={arc(c.x, c.y, r, share)} fill="none" stroke={assistedColour} strokeWidth={RING} />}
                <text x={c.x} y={c.y - 1} textAnchor="middle" fill={chart.text} fontSize={13} fontWeight="bold">{total}</text>
                <text x={c.x} y={c.y + 11} textAnchor="middle" fill={chart.axis} fontSize={9}>{Math.round(z.assisted_pct ?? 0)}%</text>
              </g>
            )
          })}
        </FibaCourtSVG>
      )}
      <figcaption className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span className="flex items-center gap-1"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: assistedColour }} />Con asistencia</span>
        <span className="flex items-center gap-1"><span aria-hidden className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: restColour, opacity: 0.55 }} />Sin asistencia</span>
        <span>Tamaño: canastas en la zona · cifra pequeña: % con asistencia</span>
        {withoutZone > 0 && <span>{withoutZone} {withoutZone === 1 ? 'canasta sin zona' : 'canastas sin zona'} no salen en la pista</span>}
      </figcaption>
    </figure>
  )
}
