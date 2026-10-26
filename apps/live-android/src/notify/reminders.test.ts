import { describe, expect, it, vi } from 'vitest'
import { loadReminderPrefs, saveReminderPrefs, syncReminders, type ReminderPlugin } from './reminders'
import type { Reminder } from './schedule'

const reminder = (id: number, code = '1'): Reminder => ({ id, at: new Date('2026-10-24T19:00:00'), title: 'LEONESA juega en 30 min', body: 'LEONESA – ZAMORA', code })

function plugin(over: Partial<ReminderPlugin> = {}): ReminderPlugin {
  return {
    checkPermissions: vi.fn().mockResolvedValue({ display: 'granted' }), requestPermissions: vi.fn().mockResolvedValue({ display: 'granted' }),
    schedule: vi.fn().mockResolvedValue(undefined), cancel: vi.fn().mockResolvedValue(undefined), getPending: vi.fn().mockResolvedValue({ notifications: [] }), ...over,
  } as ReminderPlugin
}
function memory(): Storage {
  const data = new Map<string, string>()
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: k => void data.delete(k), clear: () => data.clear(), key: () => null, get length() { return data.size } }
}

describe('syncReminders (issue #482)', () => {
  it('asks for the permission when it is needed and schedules what is planned', async () => {
    const p = plugin({ checkPermissions: vi.fn().mockResolvedValue({ display: 'prompt' }) })
    const result = await syncReminders(p, [reminder(1), reminder(2, '2')], { ask: true })
    expect(p.requestPermissions).toHaveBeenCalled()
    expect(result).toEqual({ ok: true, scheduled: 2 })
    expect((p.schedule as ReturnType<typeof vi.fn>).mock.calls[0][0].notifications.map((n: { id: number }) => n.id)).toEqual([1, 2])
  })

  it('replaces the reminders of before: it cancels the ones the app had scheduled and not the others', async () => {
    const p = plugin({ getPending: vi.fn().mockResolvedValue({ notifications: [{ id: 5, extra: { basketlab: true } }, { id: 6 }] }) })
    await syncReminders(p, [reminder(1)], { ask: false })
    expect(p.cancel).toHaveBeenCalledWith({ notifications: [{ id: 5 }] })
  })

  it('does nothing and says why when the permission is denied, without asking again if it was not asked to', async () => {
    const denied = plugin({ checkPermissions: vi.fn().mockResolvedValue({ display: 'denied' }) })
    expect(await syncReminders(denied, [reminder(1)], { ask: true })).toEqual({ ok: false, reason: 'denied', scheduled: 0 })
    expect(denied.schedule).not.toHaveBeenCalled()
    const prompt = plugin({ checkPermissions: vi.fn().mockResolvedValue({ display: 'prompt' }) })
    expect(await syncReminders(prompt, [reminder(1)], { ask: false })).toMatchObject({ ok: false, reason: 'not-asked' })
    expect(prompt.requestPermissions).not.toHaveBeenCalled()
  })

  it('without anything to schedule it only cleans up', async () => {
    const p = plugin({ getPending: vi.fn().mockResolvedValue({ notifications: [{ id: 5, extra: { basketlab: true } }] }) })
    expect(await syncReminders(p, [], { ask: false })).toEqual({ ok: true, scheduled: 0 })
    expect(p.cancel).toHaveBeenCalled()
    expect(p.schedule).not.toHaveBeenCalled()
  })

  it('a plugin that fails (a browser, an old device) is a reason, not a crash', async () => {
    const p = plugin({ checkPermissions: vi.fn().mockRejectedValue(new Error('not implemented on web')) })
    expect(await syncReminders(p, [reminder(1)], { ask: true })).toEqual({ ok: false, reason: 'unavailable', scheduled: 0 })
  })

  it('every notification carries the match code to open it and is marked as the one of the app', async () => {
    const p = plugin()
    await syncReminders(p, [reminder(1, '77')], { ask: false })
    const n = (p.schedule as ReturnType<typeof vi.fn>).mock.calls[0][0].notifications[0]
    expect(n.extra).toEqual({ basketlab: true, code: '77' })
    expect(n.schedule).toEqual({ at: new Date('2026-10-24T19:00:00'), allowWhileIdle: true })
  })
})

describe('the preferences of the reminders', () => {
  it('are off by default and keep what was chosen', () => {
    const s = memory()
    expect(loadReminderPrefs(s)).toEqual({ enabled: false, leadMin: 30 })
    saveReminderPrefs({ enabled: true, leadMin: 60 }, s)
    expect(loadReminderPrefs(s)).toEqual({ enabled: true, leadMin: 60 })
  })

  it('a corrupted or strange value falls back to the default', () => {
    const s = memory()
    s.setItem('basketlab-live-reminders', 'no json')
    expect(loadReminderPrefs(s)).toEqual({ enabled: false, leadMin: 30 })
    s.setItem('basketlab-live-reminders', JSON.stringify({ enabled: 'yes', leadMin: 7 }))
    expect(loadReminderPrefs(s)).toEqual({ enabled: false, leadMin: 30 })
  })
})

describe('opening the app from a reminder (issue #482)', () => {
  it('calls back with the match code when a reminder of the app is tapped, and stops listening', async () => {
    const { onReminderTapped } = await import('./reminders')
    const remove = vi.fn().mockResolvedValue(undefined)
    let listener: (event: { notification: { extra?: Record<string, unknown> } }) => void = () => undefined
    const p = { ...plugin(), addListener: vi.fn(async (_name: string, cb: typeof listener) => { listener = cb; return { remove } }) }
    const seen: string[] = []
    const stop = await onReminderTapped(p, code => seen.push(code))
    listener({ notification: { extra: { basketlab: true, code: '77' } } })
    listener({ notification: { extra: { other: true } } })                    // not ours
    expect(seen).toEqual(['77'])
    stop()
    expect(remove).toHaveBeenCalled()
  })

  it('without a plugin that listens there is nothing to stop', async () => {
    const { onReminderTapped } = await import('./reminders')
    expect(await onReminderTapped(plugin(), () => undefined)).toBeTypeOf('function')
  })
})


// Feedback 0.4.0 (#559): the 30-minute reminder never came and nothing on the screen said whether it had been scheduled, nor that Android 12+ delays
// the ones that are not exact. The result says which alarms are exact; the plugin is asked only when it can answer.
describe('syncReminders: exact alarms (issue #559)', () => {
  it('says whether Android lets the app set exact alarms', async () => {
    const denied = plugin({ checkExactNotificationSetting: vi.fn().mockResolvedValue({ exact_alarm: 'denied' }) })
    expect(await syncReminders(denied, [reminder(1)], { ask: false })).toEqual({ ok: true, scheduled: 1, exact: 'denied' })
    const granted = plugin({ checkExactNotificationSetting: vi.fn().mockResolvedValue({ exact_alarm: 'granted' }) })
    expect(await syncReminders(granted, [reminder(1)], { ask: false })).toEqual({ ok: true, scheduled: 1, exact: 'granted' })
  })

  it('a plugin that cannot tell, or fails telling, does not stop the reminders: the answer is left out', async () => {
    const broken = plugin({ checkExactNotificationSetting: vi.fn().mockRejectedValue(new Error('no')) })
    expect(await syncReminders(broken, [reminder(1)], { ask: false })).toEqual({ ok: true, scheduled: 1 })
  })
})
