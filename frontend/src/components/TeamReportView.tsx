/** Presentational view of a rule-based team report. */
import type { ReactNode } from 'react'
import Badge from '@/components/ui/Badge'
import type { ReportAction, ReportFinding, TeamReport } from '@/api/teamReport'

const TITLES = {
  own: {
    strengths: 'Puntos fuertes clave', weaknesses: 'Debilidades críticas',
    tactics: 'Recomendaciones tácticas', training: 'Enfoque de entrenamiento',
  },
  rival: {
    strengths: 'Peligros a neutralizar', weaknesses: 'Debilidades a explotar',
    tactics: 'Claves tácticas del partido', training: 'Plan de partido',
  },
}
const KIND_LABEL = { improve: 'Mejorar', leverage: 'Potenciar', neutralize: 'Neutralizar', exploit: 'Explotar' }
const EMPTY = 'Sin datos destacados.'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card p-5 space-y-3">
      <h2 className="text-base font-semibold text-ink-primary">{title}</h2>
      {children}
    </section>
  )
}

function Empty() {
  return <p className="text-sm text-ink-secondary">{EMPTY}</p>
}

function Findings({ rows, variant }: { rows: ReportFinding[]; variant: 'brand' | 'red' }) {
  if (!rows.length) return <Empty />
  return (
    <ul className="space-y-2">
      {rows.map(f => (
        <li key={f.key} className="text-sm text-ink-secondary">
          <Badge variant={variant} className="mr-2">Q{f.quartile}</Badge>
          <span className="font-medium text-ink-primary">{f.label}: {f.formatted}</span>
          {f.diff_pct != null && <span className="ml-1 text-xs">({f.diff_pct > 0 ? '+' : ''}{f.diff_pct.toFixed(1)}% vs mediana)</span>}
          <p className="mt-0.5">{f.text}</p>
        </li>
      ))}
    </ul>
  )
}

function Actions({ rows }: { rows: ReportAction[] }) {
  if (!rows.length) return <p className="text-sm text-ink-secondary">Sin recomendaciones destacadas.</p>
  return (
    <ul className="space-y-2">
      {rows.map(a => (
        <li key={`${a.key}-${a.area}`} className="text-sm text-ink-secondary">
          {a.priority != null && <span className="mr-2 font-mono text-ink-primary">{a.priority}.</span>}
          <Badge variant="blue" className="mr-2">{a.area}</Badge>
          <span className="font-medium text-ink-primary">{KIND_LABEL[a.kind]} · {a.label}</span>
          <p className="mt-0.5">{a.text}</p>
        </li>
      ))}
    </ul>
  )
}

export default function TeamReportView({ report }: { report: TeamReport }) {
  const t = TITLES[report.mode]
  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-secondary">
        {report.games_played} partidos analizados · comparado con los cuartiles de la competición.
      </p>
      <Section title="Perfil de equipo">
        {report.profile.length
          ? <ul className="list-disc ml-5 text-sm text-ink-secondary space-y-1">{report.profile.map(p => <li key={p}>{p}</li>)}</ul>
          : <Empty />}
      </Section>
      <Section title={t.strengths}><Findings rows={report.strengths} variant="brand" /></Section>
      <Section title={t.weaknesses}><Findings rows={report.weaknesses} variant="red" /></Section>
      <Section title="Análisis diferencial vs liga">
        {report.differentials.length ? (
          <ul className="space-y-1 text-sm text-ink-secondary">
            {report.differentials.map(d => (
              <li key={d.key}>
                <Badge variant={d.advantage ? 'brand' : 'red'} className="mr-2">{d.advantage ? 'Ventaja' : 'Desventaja'}</Badge>
                {d.label}: {d.formatted} ({d.diff_pct > 0 ? '+' : ''}{d.diff_pct.toFixed(1)}%)
              </li>
            ))}
          </ul>
        ) : <Empty />}
      </Section>
      <Section title="Consistencia partido a partido">
        {report.consistency.length ? (
          <ul className="space-y-1 text-sm text-ink-secondary">
            {report.consistency.map(c => (
              <li key={c.key}>
                <Badge variant={c.status === 'inconsistent' ? 'amber' : 'brand'} className="mr-2">
                  {c.status === 'inconsistent' ? 'Inconsistente' : 'Consistente'}
                </Badge>
                {c.label} (CV {c.cv.toFixed(0)}%). {c.text}
              </li>
            ))}
          </ul>
        ) : <Empty />}
      </Section>
      <Section title={t.tactics}><Actions rows={report.tactics} /></Section>
      <Section title={t.training}><Actions rows={report.training} /></Section>
    </div>
  )
}
