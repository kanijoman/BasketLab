/** The forecast of the match (issue #849): the probability of winning, the expected margin and the range it usually moves in, and how far to trust it. */
import { confidenceText, pct } from '@/forecast/copy'
import type { MatchPreview } from '@/forecast/preview'
import StatCard from '@/components/ui/StatCard'
import ToneBadge from './ToneBadge'
import { signed } from './format'

export default function Forecast({ preview, ownName }: { preview: MatchPreview; ownName: string }) {
  const { headline, confidence } = preview
  const tone = headline.p >= 0.6 ? 'ok' : headline.p <= 0.4 ? 'bad' : 'warn'
  return (
    <section aria-label="Pronóstico" className="space-y-3">
      <h2 className="text-lg font-semibold text-ink">Pronóstico</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Probabilidad de victoria" value={pct(headline.p, 0)} sub={`de ${ownName}`} tone={tone} />
        <StatCard label="Margen esperado" value={`${signed(headline.mu)} pts`} sub="positivo: gana nuestro equipo" />
        <StatCard label="Rango habitual" value={`de ${signed(headline.range80[0], 0)} a ${signed(headline.range80[1], 0)}`} sub="el 80 % de los partidos como este" />
      </div>
      <div className="flex flex-wrap items-start gap-2">
        <ToneBadge tone={confidence.level === 'baja' ? 'warn' : 'ok'}>{confidence.level === 'baja' ? 'Confianza baja' : 'Confianza normal'}</ToneBadge>
        {confidence.reasons.length > 0 && (
          <ul className="text-sm text-ink-muted">
            {confidence.reasons.map((reason, i) => <li key={i}>{confidenceText(reason)}</li>)}
          </ul>
        )}
      </div>
      {!preview.detail && <p className="text-sm text-ink-muted">Aún hay muy pocos partidos jugados para describir escenarios y objetivos: solo se muestra el pronóstico.</p>}
    </section>
  )
}
