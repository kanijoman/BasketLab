/** Keeps the reminders of the matches of the teams of interest scheduled while the option is on (issue #482). */
import { useCallback, useEffect, useRef, useState } from 'react'
import { capacitorReminderPlugin, loadReminderPrefs, saveReminderPrefs, syncReminders, type ReminderPlugin, type ReminderPrefs, type SyncResult } from '../notify/reminders'
import { planReminders } from '../notify/schedule'
import type { NextMatch } from '../package/upcoming'

export interface ReminderLoader {
  load: () => Promise<ReminderPlugin | null>
}

const DEFAULT_LOADER: ReminderLoader = { load: capacitorReminderPlugin }

export function useReminders(next: NextMatch[], now: Date, loader: ReminderLoader = DEFAULT_LOADER) {
  const [prefs, setPrefs] = useState<ReminderPrefs>(() => loadReminderPrefs())
  const [result, setResult] = useState<SyncResult | null>(null)
  const justTurnedOn = useRef(false)
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const plan = prefs.enabled ? planReminders(next, now, prefs.leadMin) : []
  // the plan as text: the effect runs when what is planned changes, not on every render
  const planKey = JSON.stringify(plan.map(r => [r.id, r.at.getTime(), r.title]))

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const plugin = await loaderRef.current.load()
      if (cancelled) return
      if (!plugin) { if (prefs.enabled) setResult({ ok: false, reason: 'unavailable', scheduled: 0 }); return }
      const ask = justTurnedOn.current
      justTurnedOn.current = false
      const outcome = await syncReminders(plugin, plan, { ask })
      if (!cancelled && prefs.enabled) setResult(outcome)
    })()
    return () => { cancelled = true }
  }, [planKey, prefs.enabled])   // eslint-disable-line react-hooks/exhaustive-deps

  const update = useCallback((patch: Partial<ReminderPrefs>) => {
    setPrefs(previous => {
      const nextPrefs = { ...previous, ...patch }
      if (patch.enabled && !previous.enabled) justTurnedOn.current = true
      saveReminderPrefs(nextPrefs)
      return nextPrefs
    })
    if (patch.enabled === false) setResult(null)
  }, [])

  /** Opens the system screen of the exact alarms and schedules again with what the user decided (#559). */
  const allowExact = useCallback(async () => {
    const plugin = await loaderRef.current.load()
    if (!plugin?.changeExactNotificationSetting) return
    try { await plugin.changeExactNotificationSetting() } catch { /* the screen could not be opened: the note stays */ }
    setResult(await syncReminders(plugin, plan, { ask: false }))
  }, [planKey])   // eslint-disable-line react-hooks/exhaustive-deps

  return { prefs, result, update, plan, allowExact }
}
