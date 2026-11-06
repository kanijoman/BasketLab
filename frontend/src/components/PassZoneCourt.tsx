/** From where the players a passer finds score, on one court (issue #773, the passer's side).
 *  One bubble per zone: its size is the number of assists that end there; the small figure is the share of all his assists (those with no known zone count in the total). */
import type { PassZone } from '@/api/assistConnections'
import FibaCourtSVG, { ZONE_CENTERS } from '@/components/ui/FibaCourtSVG'
import { useChartTheme } from '@/lib/chartTheme'

interface Props {
  zones: PassZone[]
  /** Assists whose basket has no known zone (no shot coordinates): in the total of the percentages and said under the court. */
  withoutZone?: number
}

export default function PassZoneCourt({ zones, withoutZone = 0 }: Props) {
  const chart = useChartTheme()
  const drawn = zones.filter(z => z.count > 0 && ZONE_CENTERS[z.zone])
  const total = drawn.reduce((sum, z) => sum + z.count, 0) + withoutZone
  const max = Math.max(1, ...drawn.map(z => z.count))
  return (
    <figure className="flex flex-col items-center gap-2">
      {drawn.length === 0 ? (
        <p className="text-sm text-ink-muted py-8">Sin asistencias con zona conocida para este jugador.</p>
      ) : (
        <FibaCourtSVG vizMode="scatter">
          {drawn.map(z => {
            const c = ZONE_CENTERS[z.zone]
            const r = 17 + 13 * Math.sqrt(z.count / max)
            return (
              <g key={z.zone} data-pass-zone={z.zone}>
                <title>{`${c.label}: ${z.count} ${z.count === 1 ? 'asistencia acaba' : 'asistencias acaban'} en canasta desde aquí`}</title>
                <circle cx={c.x} cy={c.y} r={r} fill={chart.floor} />
                <circle cx={c.x} cy={c.y} r={r} fill="none" stroke={chart.series[0]} strokeWidth={7} />
                <text x={c.x} y={c.y - 1} textAnchor="middle" fill={chart.text} fontSize={13} fontWeight="bold">{z.count}</text>
                <text x={c.x} y={c.y + 11} textAnchor="middle" fill={chart.axis} fontSize={9}>{Math.round((100 * z.count) / total)}%</text>
              </g>
            )
          })}
        </FibaCourtSVG>
      )}
      <figcaption className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span>Tamaño: asistencias que acaban en canasta desde la zona · cifra pequeña: % de sus asistencias</span>
        {withoutZone > 0 && <span>{withoutZone} {withoutZone === 1 ? 'asistencia sin zona' : 'asistencias sin zona'} no salen en la pista</span>}
      </figcaption>
    </figure>
  )
}
