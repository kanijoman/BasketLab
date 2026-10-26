/**
 * Local notifications of the matches of the teams of interest (issue #482). No server and no push: the app schedules them on the device when the
 * list is read, and replaces them every time (a match that moved, a team that is no longer of interest). The plugin hides behind a small interface so
 * everything is tested without a device; in a browser it is simply unavailable. Limit: if the app is not opened after a round is published it does
 * not know the match yet.
 */
import { DEFAULT_LEAD_MIN, LEAD_OPTIONS, type Reminder } from './schedule'

const KEY = 'basketlab-live-reminders'

export interface ReminderPrefs {
  enabled: boolean
  leadMin: number
}

export function loadReminderPrefs(storage: Storage = localStorage): ReminderPrefs {
  try {
    const raw = JSON.parse(storage.getItem(KEY) ?? '{}')
    return { enabled: raw.enabled === true, leadMin: LEAD_OPTIONS.includes(raw.leadMin) ? raw.leadMin : DEFAULT_LEAD_MIN }
  } catch {
    return { enabled: false, leadMin: DEFAULT_LEAD_MIN }
  }
}

export function saveReminderPrefs(prefs: ReminderPrefs, storage: Storage = localStorage): void {
  try {
    storage.setItem(KEY, JSON.stringify(prefs))
  } catch {
    /* blocked storage: it is chosen again next time */
  }
}

/** The part of `@capacitor/local-notifications` that is used. */
export interface ReminderPlugin {
  checkPermissions(): Promise<{ display: string }>
  requestPermissions(): Promise<{ display: string }>
  schedule(options: { notifications: Array<Record<string, unknown>> }): Promise<unknown>
  cancel(options: { notifications: Array<{ id: number }> }): Promise<void>
  getPending(): Promise<{ notifications: Array<{ id: number; extra?: Record<string, unknown> | null }> }>
  /** Android 12+: whether the app may set exact alarms (without it the reminders can come minutes late, #559). Absent in a browser. */
  checkExactNotificationSetting?(): Promise<{ exact_alarm: string }>
  /** Opens the system screen where the user allows the exact alarms. */
  changeExactNotificationSetting?(): Promise<{ exact_alarm: string }>
  addListener?(name: 'localNotificationActionPerformed', callback: (event: { notification: { extra?: Record<string, unknown> | null } }) => void): Promise<{ remove: () => Promise<void> }>
}

export type SyncResult = { ok: true; scheduled: number; exact?: 'granted' | 'denied' } | { ok: false; reason: 'denied' | 'not-asked' | 'unavailable'; scheduled: 0 }

/** ``{exact}`` when the plugin can say whether Android allows exact alarms; nothing when it cannot (it must never stop the reminders). */
async function exactAlarms(plugin: ReminderPlugin): Promise<{ exact?: 'granted' | 'denied' }> {
  try {
    if (!plugin.checkExactNotificationSetting) return {}
    return { exact: (await plugin.checkExactNotificationSetting()).exact_alarm === 'granted' ? 'granted' : 'denied' }
  } catch {
    return {}
  }
}

/** Replaces the reminders of the app with `reminders`. `ask`: it may show the permission dialog (when the user has just turned the reminders on). */
export async function syncReminders(plugin: ReminderPlugin, reminders: Reminder[], opts: { ask: boolean }): Promise<SyncResult> {
  try {
    let permission = (await plugin.checkPermissions()).display
    if (permission !== 'granted' && opts.ask && permission !== 'denied') permission = (await plugin.requestPermissions()).display
    if (permission !== 'granted') return { ok: false, reason: permission === 'denied' ? 'denied' : 'not-asked', scheduled: 0 }
    const mine = (await plugin.getPending()).notifications.filter(n => n.extra && n.extra.basketlab === true)
    if (mine.length > 0) await plugin.cancel({ notifications: mine.map(n => ({ id: n.id })) })
    if (reminders.length > 0) {
      await plugin.schedule({
        notifications: reminders.map(r => ({
          id: r.id, title: r.title, body: r.body, extra: { basketlab: true, code: r.code }, schedule: { at: r.at, allowWhileIdle: true },
        })),
      })
    }
    return { ok: true, scheduled: reminders.length, ...(await exactAlarms(plugin)) }
  } catch {
    return { ok: false, reason: 'unavailable', scheduled: 0 }
  }
}

/** The real plugin, loaded only when it is used (the web build and the tests never load it); null in a browser. */
export async function capacitorReminderPlugin(): Promise<ReminderPlugin | null> {
  try {
    const { Capacitor } = await import('@capacitor/core')
    if (!Capacitor.isNativePlatform()) return null
    return (await import('@capacitor/local-notifications')).LocalNotifications as unknown as ReminderPlugin
  } catch {
    return null
  }
}

/** Tells which match a reminder of the app was tapped for, to open it; returns the function that stops listening. */
export async function onReminderTapped(plugin: ReminderPlugin, callback: (code: string) => void): Promise<() => void> {
  try {
    const handle = await plugin.addListener?.('localNotificationActionPerformed', event => {
      const extra = event.notification.extra
      if (extra && extra.basketlab === true && typeof extra.code === 'string') callback(extra.code)
    })
    return () => { void handle?.remove() }
  } catch {
    return () => undefined
  }
}
