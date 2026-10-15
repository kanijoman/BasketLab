import { useRef } from 'react'
import AlertCard, { CATEGORY_LABEL } from './AlertCard'
import type { Alert } from '../engine/types'
import type { Verdict } from '../feedback/store'
import { useAlertFilter } from './useAlertFilter'

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

/** The keys that arrived with the latest change of the list (issue #312): they enter with a highlight. The first render has none, so
 *  opening a tab or the app does not animate the whole list; rendering the same list again keeps the same ones marked. */
function useFreshKeys(entries: AlertEntry[]): Set<string> {
  const state = useRef<{ known: Set<string> | null; fresh: Set<string> }>({ known: null, fresh: new Set() })
  const keys = entries.map(e => e.alert.key)
  const { known } = state.current
  if (known === null) {
    state.current = { known: new Set(keys), fresh: new Set() }
  } else {
    const added = keys.filter(k => !known.has(k))
    if (added.length > 0) state.current = { known: new Set(keys), fresh: new Set(added) }
  }
  return state.current.fresh
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
 * category are marks of each card (colour, icon, label); the counters of the header count them and are also the filter (#322): pressing
 * one hides or shows that severity. The filter goes first, then the 20 latest are visible and the rest collapsed.
 */
export default function AlertList({ entries, verdicts = {}, onVerdict }: ListProps) {
  const { critical, warning, info } = countBySeverity(entries)
  const fresh = useFreshKeys(entries)
  const { hidden, toggle } = useAlertFilter()
  const counter = (severity: Alert['severity'], n: number, one: string, many: string) => n > 0 && (
    <button type="button" className={`count count-${severity}`} aria-pressed={!hidden.has(severity)} onClick={() => toggle(severity)}>
      {plural(n, one, many)}
    </button>
  )
  const shown = entries.filter(e => !hidden.has(e.alert.severity))
  const card = (e: AlertEntry) => (
    <AlertCard key={e.alert.key} alert={e.alert} at={e.at} verdict={verdicts[e.alert.key] ?? null} fresh={fresh.has(e.alert.key)}
      onVerdict={onVerdict && (v => onVerdict(e.alert.key, v))} />
  )
  const older = shown.slice(VISIBLE_ALERTS)
  return (
    <div className="alert-list">
      <p className="alert-counts" aria-label="Resumen de alertas">
        {counter('critical', critical, 'crítica', 'críticas')}
        {counter('warning', warning, 'aviso', 'avisos')}
        {counter('info', info, 'informativa', 'informativas')}
      </p>
      {shown.length === 0 && entries.length > 0 && (
        <p className="detail">Has ocultado todas las alertas: pulsa un contador para volver a verlas.</p>
      )}
      <ul className="alerts">{shown.slice(0, VISIBLE_ALERTS).map(card)}</ul>
      {older.length > 0 && (
        <details className="alerts-older">
          <summary>{older.length === 1 ? 'Ver la 1 anterior' : `Ver las ${older.length} anteriores`}</summary>
          <ul className="alerts">{older.map(card)}</ul>
        </details>
      )}
    </div>
  )
}
