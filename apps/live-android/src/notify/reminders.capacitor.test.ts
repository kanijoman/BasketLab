/**
 * The reminders with Capacitor's REAL plugin object (follow-up of #697, feedback of the 0.5.2): `registerPlugin` gives a Proxy that answers every property, `then`
 * included, so it must reach the reminders without being taken for a promise. The device is faked only at its border: the platform says it is native and the plugin's
 * implementation is a small object; the Proxy in between is Capacitor's own.
 */
import { describe, expect, it, vi } from 'vitest'
import { capacitorReminderPlugin, onReminderTapped, syncReminders, type ReminderPlugin } from './reminders'

const device = vi.hoisted(() => ({
  permission: 'prompt',
  scheduled: [] as unknown[],
  tapped: null as null | ((event: { notification: { extra: Record<string, unknown> } }) => void),
}))

vi.mock('@capacitor/core', async importOriginal => {
  const actual = await importOriginal<typeof import('@capacitor/core')>()
  return { ...actual, Capacitor: { ...actual.Capacitor, isNativePlatform: () => true } }
})

vi.mock('@capacitor/local-notifications', async () => {
  const { registerPlugin } = await vi.importActual<typeof import('@capacitor/core')>('@capacitor/core')
  const implementation = {
    checkPermissions: async () => ({ display: device.permission }),
    requestPermissions: async () => { device.permission = 'granted'; return { display: device.permission } },
    schedule: async (options: { notifications: unknown[] }) => { device.scheduled.push(...options.notifications); return { notifications: [] } },
    cancel: async () => undefined,
    getPending: async () => ({ notifications: [] }),
    checkExactNotificationSetting: async () => ({ exact_alarm: 'granted' }),
    changeExactNotificationSetting: async () => ({ exact_alarm: 'granted' }),
    addListener: async (_name: string, callback: typeof device.tapped) => { device.tapped = callback; return { remove: async () => undefined } },
  }
  return { LocalNotifications: registerPlugin('LocalNotifications', { web: implementation }) }
})

const HUNG = 'hung'
const settled = <T>(promise: Promise<T>) => Promise.race([promise, new Promise<typeof HUNG>(resolve => setTimeout(() => resolve(HUNG), 300))])

describe('capacitorReminderPlugin with the real Capacitor plugin (feedback 0.5.2)', () => {
  it('loads: the plugin is not taken for a promise, so the permission is asked and the reminders are scheduled', async () => {
    const plugin = await settled(capacitorReminderPlugin())
    expect(plugin).not.toBe(HUNG)
    const result = await syncReminders(plugin as ReminderPlugin,
      [{ id: 7, at: new Date('2026-11-14T17:30:00'), title: 'LEONESA juega en 30 min', body: 'LEONESA – ZAMORA', code: '2524501' }], { ask: true })
    expect(result).toEqual({ ok: true, scheduled: 1, exact: 'granted' })
    expect(device.permission).toBe('granted')
    expect(device.scheduled).toHaveLength(1)
  })

  it('a tapped reminder opens its match through the same plugin', async () => {
    const plugin = await settled(capacitorReminderPlugin())
    expect(plugin).not.toBe(HUNG)
    const opened: string[] = []
    await onReminderTapped(plugin as ReminderPlugin, code => opened.push(code))
    device.tapped?.({ notification: { extra: { basketlab: true, code: '2524501' } } })
    expect(opened).toEqual(['2524501'])
  })
})
