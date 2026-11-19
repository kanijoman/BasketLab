// The radar of a player of Talent (B4, #880): the percentiles of ONE row in its competition, eight axes in a fixed order, 0 in the centre and 100 on the rim. Colours come from the theme (`useChartTheme`),
// the axes without a value are left out of the polygon (never drawn as a zero) and the numbers are in the list beside it, so the picture is never the only way to read it.
import { useChartTheme } from '@/lib/chartTheme'
import type { RadarAxis } from './player'

const SIZE = 280
const CENTRE = SIZE / 2
const RADIUS = 96
const RINGS = [25, 50, 75, 100]

const point = (index: number, count: number, value: number): [number, number] => {
  const angle = -Math.PI / 2 + (index / count) * 2 * Math.PI
  const r = (value / 100) * RADIUS
  return [CENTRE + r * Math.cos(angle), CENTRE + r * Math.sin(angle)]
}

export default function PlayerRadar({ axes, name }: { axes: RadarAxis[]; name: string }) {
  const chart = useChartTheme()
  const known = axes.map((a, i) => ({ a, i })).filter(x => x.a.value !== null)
  const polygon = known.map(({ a, i }) => point(i, axes.length, a.value as number).join(',')).join(' ')
  const description = known.length ? known.map(({ a }) => `${a.short} ${Math.round(a.value as number)}`).join(', ') : 'sin datos'
  return (
    <svg role="img" aria-label={`Perfil de ${name}: percentiles ${description}`} viewBox={`0 0 ${SIZE} ${SIZE}`} className="mx-auto h-auto w-full max-w-xs">
      {RINGS.map(ring => (
        <polygon key={ring} points={axes.map((_, i) => point(i, axes.length, ring).join(',')).join(' ')} fill="none" stroke={chart.grid} strokeWidth={ring === 100 ? 1.5 : 1} />
      ))}
      {axes.map((a, i) => {
        const [x, y] = point(i, axes.length, 100)
        const [lx, ly] = point(i, axes.length, 120)
        return (
          <g key={a.key}>
            <line x1={CENTRE} y1={CENTRE} x2={x} y2={y} stroke={chart.grid} />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize="10" fill={chart.axis}>{a.short}</text>
          </g>
        )
      })}
      {known.length >= 3 && <polygon points={polygon} fill={chart.series[0]} fillOpacity={0.25} stroke={chart.series[0]} strokeWidth={2} />}
      {known.map(({ a, i }) => {
        const [x, y] = point(i, axes.length, a.value as number)
        return <circle key={a.key} cx={x} cy={y} r={3} fill={chart.series[0]} />
      })}
    </svg>
  )
}
