import AlertCard, { CATEGORY_LABEL } from './AlertCard'
import type { Alert } from '../engine/types'
import type { Verdict } from '../feedback/store'

export interface AlertEntry { alert: Alert; at: string }

export { CATEGORY_LABEL }

/** The alerts shown in the flow; the older ones wait behind a summary (issue #313: a long page to scroll was the complaint). */
export const VISIBLE_ALERTS = 20

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** Counts per severity, for the header. */
export function countBySeverity(entries: AlertEntry[]) {
  const by = (s: Alert['severity']) => entries.filter(e => e.alert.severity === s).length
  return { critical: by('critical'), warning: by('warning'), info: by('info') }
}

interface ListProps {
  /** The latest first (the app prepends every new alert). */
  entries: AlertEntry[]
  /** Answer of the staff per alert key, and the way to give one (issue #235). */
  verdicts?: Record<string, Verdict | null>
  onVerdict?: (key: string, verdict: Verdict | null) => void
}

/**
 * One chronological flow, the latest alert on top (issue #313; before it the list was grouped by severity, #229). Severity and
 * category are marks of each card (colour, icon, label), the header counts them. The 20 latest are visible, the rest collapsed.
 */
export default function AlertList({ entries, verdicts = {}, onVerdict }: ListProps) {
  const { critical, warning, info } = countBySeverity(entries)
  const card = (e: AlertEntry) => (
    <AlertCard key={e.alert.key} alert={e.alert} at={e.at} verdict={verdicts[e.alert.key] ?? null}
      onVerdict={onVerdict && (v => onVerdict(e.alert.key, v))} />
  )
  const older = entries.slice(VISIBLE_ALERTS)
  return (
    <div className="alert-list">
      <p className="alert-counts" aria-label="Resumen de alertas">
        {critical > 0 && <span className="count count-critical">{plural(critical, 'crítica', 'críticas')}</span>}
        {warning > 0 && <span className="count count-warning">{plural(warning, 'aviso', 'avisos')}</span>}
        {info > 0 && <span className="count count-info">{plural(info, 'informativa', 'informativas')}</span>}
      </p>
      <ul className="alerts">{entries.slice(0, VISIBLE_ALERTS).map(card)}</ul>
      {older.length > 0 && (
        <details className="alerts-older">
          <summary>{older.length === 1 ? 'Ver la 1 anterior' : `Ver las ${older.length} anteriores`}</summary>
          <ul className="alerts">{older.map(card)}</ul>
        </details>
      )}
    </div>
  )
}
