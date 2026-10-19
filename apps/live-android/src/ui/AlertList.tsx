import { useRef, useState } from 'react'
import AlertCard, { CATEGORY_LABEL } from './AlertCard'
import type { Alert } from '../engine/types'
import type { Verdict } from '../feedback/store'
import { useAlertFilter } from './useAlertFilter'

export interface AlertEntry { alert: Alert; at: string }

export { CATEGORY_LABEL }

/** The previous quarter folds by itself this many game-seconds into the next one (issue #406). */
export const AUTO_FOLD_S = 120

/** The period an alert was said in, from its clock label ("Q2 05:30", "PR1 03:00"); 1 when it cannot be read. */
export function periodOfLabel(at: string): number {
  const m = /^(Q|PR)(\d+)/.exec(at)
  return m ? (m[1] === 'PR' ? 4 : 0) + Number(m[2]) : 1
}

const periodSeconds = (period: number) => (period > 4 ? 300 : 600)
const periodTitle = (period: number) => (period > 4 ? `Prórroga ${period - 4}` : `Cuarto ${period}`)

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
  /** The game clock now: it decides which quarter is the current one and when the previous folds. Without it the newest alert says. */
  clock?: { period: number; remaining: number }
}

/**
 * One chronological flow, the latest alert on top (issue #313; before it the list was grouped by severity, #229). Severity and
 * category are marks of each card (colour, icon, label); the counters of the header count them and are also the filter (#322): pressing
 * one hides or shows that severity. The filter goes first. The flow is split in one foldable group per quarter (#406): the current one is
 * open, the previous one folds by itself ``AUTO_FOLD_S`` into the next, and what the staff opens or folds by hand is kept.
 */
export default function AlertList({ entries, verdicts = {}, onVerdict, clock }: ListProps) {
  const [manual, setManual] = useState<Record<number, boolean>>({})
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
  const current = clock?.period ?? (entries.length > 0 ? periodOfLabel(entries[0].at) : 1)
  const into = clock ? periodSeconds(clock.period) - clock.remaining : 0
  const isOpen = (period: number) => manual[period] ?? (period >= current || (period === current - 1 && into < AUTO_FOLD_S))
  const groups: { period: number; items: AlertEntry[] }[] = []
  for (const e of shown) {
    const period = periodOfLabel(e.at)
    const last = groups[groups.length - 1]
    if (last && last.period === period) last.items.push(e)
    else groups.push({ period, items: [e] })
  }
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
      {groups.map(({ period, items }) => (
        <details key={period} className="alert-period" open={isOpen(period)}>
          <summary onClick={e => { e.preventDefault(); setManual(m => ({ ...m, [period]: !isOpen(period) })) }}>
            {periodTitle(period)} · {plural(items.length, 'alerta', 'alertas')}
          </summary>
          <ul className="alerts">{items.map(card)}</ul>
        </details>
      ))}
    </div>
  )
}
