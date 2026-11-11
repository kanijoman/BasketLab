/** The scenarios of the match (issue #849): how the margin is spread (wins in the colour of the good, losses in the colour of the bad) and the four kinds of game with how they come about. */
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { highlightText, pct, SCENARIO_TEXT } from '@/forecast/copy'
import type { PreviewDetail } from '@/forecast/preview'
import { useChartTheme } from '@/lib/chartTheme'
import Card from '@/components/ui/Card'
import { signed } from './format'

const RANGE = 30            // the chart shows the margins from -30 to 30: the rest is in the cards

export default function ScenariosChart({ detail }: { detail: PreviewDetail }) {
  const chart = useChartTheme()
  const data = detail.density.filter(d => Math.abs(d.margin) <= RANGE).map(d => ({ margin: d.margin, p: d.p * 100 }))
  return (
    <section aria-label="Escenarios" className="space-y-3">
      <h2 className="text-lg font-semibold text-ink">Escenarios</h2>
      <p className="text-sm text-ink-muted">Cómo suelen acabar los partidos como este, por la diferencia de puntos a favor de nuestro equipo. Salen de los partidos reales de la competición.</p>
      <div className="h-56 w-full" role="img" aria-label="Probabilidad de cada diferencia de puntos">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
            <XAxis dataKey="margin" tick={{ fill: chart.axis, fontSize: 11 }} tickFormatter={(v: number) => signed(v, 0)} interval={4} stroke={chart.grid} />
            <YAxis tick={{ fill: chart.axis, fontSize: 11 }} tickFormatter={(v: number) => `${v.toFixed(0)} %`} width={36} stroke={chart.grid} />
            <Tooltip contentStyle={chart.tooltip} formatter={(v: number) => [`${v.toFixed(1).replace('.', ',')} %`, 'Probabilidad']} labelFormatter={(v: number) => `Diferencia de ${signed(v, 0)} puntos`} />
            <ReferenceLine x={0} stroke={chart.reference} />
            <Bar dataKey="p" isAnimationActive={false}>
              {data.map(d => <Cell key={d.margin} fill={d.margin > 0 ? chart.ok : d.margin < 0 ? chart.bad : chart.faint} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {detail.scenarios.map(b => (
          <Card key={b.id} title={SCENARIO_TEXT[b.id].title} padding="md">
            <p className="text-2xl font-bold text-ink">{pct(b.p, 0)}</p>
            <p className="text-xs text-ink-muted">{SCENARIO_TEXT[b.id].hint}</p>
            <ul className="mt-2 space-y-1 text-xs text-ink-muted">
              {b.highlights.map(h => <li key={`${h.side}-${h.factor}`}>{highlightText(h)}</li>)}
            </ul>
          </Card>
        ))}
      </div>
    </section>
  )
}
