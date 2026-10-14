import AlertCard, { CATEGORY_LABEL } from './AlertCard'
import type { Alert } from '../engine/types'
import type { Verdict } from '../feedback/store'

export interface AlertEntry { alert: Alert; at: string }

export { CATEGORY_LABEL }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** Critical first, then warnings, then the informative ones in their own block (always visible: collapsed they were overlooked,
 *  issue #309). Stable inside a level. */
export function splitBySeverity(entries: AlertEntry[]) {
  const by = (s: Alert['severity']) => entries.filter(e => e.alert.severity === s)
  return { critical: by('critical'), warning: by('warning'), info: by('info') }
}

interface ListProps {
  entries: AlertEntry[]
  /** Answer of the staff per alert key, and the way to give one (issue #235). */
  verdicts?: Record<string, Verdict | null>
  onVerdict?: (key: string, verdict: Verdict | null) => void
}

export default function AlertList({ entries, verdicts = {}, onVerdict }: ListProps) {
  const { critical, warning, info } = splitBySeverity(entries)
  const card = (e: AlertEntry) => (
    <AlertCard key={e.alert.key} alert={e.alert} at={e.at} verdict={verdicts[e.alert.key] ?? null}
      onVerdict={onVerdict && (v => onVerdict(e.alert.key, v))} />
  )
  return (
    <div className="alert-list">
      <p className="alert-counts" aria-label="Resumen de alertas">
        {critical.length > 0 && <span className="count count-critical">{plural(critical.length, 'crítica', 'críticas')}</span>}
        {warning.length > 0 && <span className="count count-warning">{plural(warning.length, 'aviso', 'avisos')}</span>}
        {info.length > 0 && <span className="count count-info">{plural(info.length, 'informativa', 'informativas')}</span>}
      </p>
      <ul className="alerts">{[...critical, ...warning].map(card)}</ul>
      {info.length > 0 && (
        <section className="alerts-info" aria-label="Informativas">
          <h3>Informativas ({info.length})</h3>
          <ul className="alerts">{info.map(card)}</ul>
        </section>
      )}
    </div>
  )
}
