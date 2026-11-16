import { useCallback, useMemo, useRef, useState } from 'react'
import type { Alert } from '../engine/types'
import { FeedbackStore, type FeedbackRecord, type StorageLike, type Verdict } from './store'

/**
 * What the staff did with the alerts of one match (``context``): since #933 only dismissing (``descartada``), still saved per match. ``register`` is stable so the engine output
 * handler can call it; the store follows the context, so a change of match starts a separate history.
 */
export function useFeedback(context: string, packageId: string | null, storage?: StorageLike | null) {
  const store = useMemo(() => new FeedbackStore(context, packageId, storage), [context, packageId, storage])
  const latest = useRef(store)
  latest.current = store
  const [version, setVersion] = useState(0)
  const bump = () => setVersion(v => v + 1)

  const register = useCallback((alert: Alert, elapsed: number) => {
    const isNew = !latest.current.get(alert.key)
    latest.current.register(alert, elapsed, new Date().toISOString())
    if (isNew) setVersion(v => v + 1)
  }, [])
  const setVerdict = useCallback((key: string, verdict: Verdict | null) => {
    latest.current.setVerdict(key, verdict, new Date().toISOString())
    bump()
  }, [])

  // `version` makes the derived values follow every change of the store.
  const records: FeedbackRecord[] = useMemo(() => store.records(), [store, version])  // eslint-disable-line react-hooks/exhaustive-deps
  const verdicts = useMemo(() => Object.fromEntries(records.map(r => [r.key, r.verdict])), [records])

  return { records, verdicts, register, setVerdict }
}
