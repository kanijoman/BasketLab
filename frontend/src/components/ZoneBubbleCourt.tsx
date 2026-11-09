/** One court with one bubble per zone, shared by the connections' courts (issue #773, #803): `AssistZoneCourt` (the baskets a player scores, assisted against not) and `PassZoneCourt` (the baskets his assists end in).
 *  A bubble's size is its `total`; the ring is an arc from the top, clockwise, of its `share` (0-1) over a faint track of the whole circle; the small figure is `percent`.
 *  What differs between the courts is only the data, the texts and the legend, which the caller gives: the drawing is written once. */
import type { ReactNode } from 'react'
import FibaCourtSVG, { ZONE_CENTERS } from '@/components/ui/FibaCourtSVG'
import { useChartTheme } from '@/lib/chartTheme'

const RING = 7

/** The arc of a ring of radius `r` centred on (cx, cy), from the top, clockwise, covering `share` of the circle (0 < share < 1). */
function arc(cx: number, cy: number, r: number, share: number): string {
  const angle = share * 2 * Math.PI
  return `M ${cx} ${cy - r} A ${r} ${r} 0 ${share > 0.5 ? 1 : 0} 1 ${cx + r * Math.sin(angle)} ${cy - r * Math.cos(angle)}`
}

export interface ZoneBubble {
  zone: string
  /** What the bubble counts (its size). */
  total: number
  /** The part of the ring that is coloured, 0-1. */
  share: number
  /** The small figure, already rounded. */
  percent: number
  /** The tooltip. */
  title: string
}

interface Props {
  bubbles: ZoneBubble[]
  /** The attribute that marks each bubble's group (the pages and their tests find them by it). */
  marker: 'data-zone' | 'data-pass-zone'
  /** What is said when there is nothing to draw. */
  empty: string
  /** The caption under the court: its legend and notes. */
  children?: ReactNode
}

export default function ZoneBubbleCourt({ bubbles, marker, empty, children }: Props) {
  const chart = useChartTheme()
  const drawn = bubbles.filter(b => b.total > 0 && ZONE_CENTERS[b.zone])
  const max = Math.max(1, ...drawn.map(b => b.total))
  return (
    <figure className="flex flex-col items-center gap-2">
      {drawn.length === 0 ? (
        <p className="text-sm text-ink-muted py-8">{empty}</p>
      ) : (
        <FibaCourtSVG vizMode="scatter">
          {drawn.map(b => {
            const c = ZONE_CENTERS[b.zone]
            const r = 17 + 13 * Math.sqrt(b.total / max)
            return (
              <g key={b.zone} {...{ [marker]: b.zone }}>
                <title>{b.title}</title>
                <circle cx={c.x} cy={c.y} r={r} fill={chart.floor} />
                <circle cx={c.x} cy={c.y} r={r} fill="none" stroke={b.share >= 1 ? chart.series[0] : chart.faint} strokeWidth={RING} strokeOpacity={b.share >= 1 ? 1 : 0.55} />
                {b.share > 0 && b.share < 1 && <path d={arc(c.x, c.y, r, b.share)} fill="none" stroke={chart.series[0]} strokeWidth={RING} />}
                <text x={c.x} y={c.y - 1} textAnchor="middle" fill={chart.text} fontSize={13} fontWeight="bold">{b.total}</text>
                <text x={c.x} y={c.y + 11} textAnchor="middle" fill={chart.axis} fontSize={9}>{b.percent}%</text>
              </g>
            )
          })}
        </FibaCourtSVG>
      )}
      <figcaption className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-ink-muted">{children}</figcaption>
    </figure>
  )
}
