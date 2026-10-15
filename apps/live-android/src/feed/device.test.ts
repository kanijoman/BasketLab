// The tablet side of the live mode (issues #219, #220): keep the screen on while the connection runs, and tell when the app
// comes back to the foreground or the network is back. The Capacitor plugins are replaced by fakes.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const plugins = vi.hoisted(() => {
  const handlers: Record<string, (event: never) => void> = {}
  const listener = (name: string) => vi.fn(async (_event: string, cb: (event: never) => void) => {
    handlers[name] = cb
    return { remove: vi.fn(async () => { delete handlers[name] }) }
  })
  return {
    handlers,
    keepAwake: vi.fn(async () => undefined), allowSleep: vi.fn(async () => undefined),
    appListener: listener('app'), networkListener: listener('network'),
  }
})

vi.mock('@capacitor-community/keep-awake', () => ({ KeepAwake: { keepAwake: plugins.keepAwake, allowSleep: plugins.allowSleep } }))
vi.mock('@capacitor/app', () => ({ App: { addListener: plugins.appListener } }))
vi.mock('@capacitor/network', () => ({ Network: { addListener: plugins.networkListener } }))

import { capacitorDevice } from './device'

beforeEach(() => {
  vi.clearAllMocks()
  for (const key of Object.keys(plugins.handlers)) delete plugins.handlers[key]
})

describe('capacitorDevice', () => {
  it('keeps the screen on and lets it sleep again', async () => {
    await expect(capacitorDevice.keepAwake()).resolves.toBe(true)
    expect(plugins.keepAwake).toHaveBeenCalledTimes(1)
    await capacitorDevice.allowSleep()
    expect(plugins.allowSleep).toHaveBeenCalledTimes(1)
  })

  it('a plugin that fails (an old WebView, no wake lock) never breaks the live mode', async () => {
    plugins.keepAwake.mockRejectedValueOnce(new Error('not supported'))
    plugins.allowSleep.mockRejectedValueOnce(new Error('not supported'))
    await expect(capacitorDevice.keepAwake()).resolves.toBe(false)
    await expect(capacitorDevice.allowSleep()).resolves.toBeUndefined()
  })

  it('tells the reason when the app returns to the foreground or the network is back, and nothing otherwise', async () => {
    const seen: string[] = []
    const stop = capacitorDevice.onResume(reason => seen.push(reason))
    await vi.waitFor(() => expect(Object.keys(plugins.handlers).sort()).toEqual(['app', 'network']))
    plugins.handlers.app({ isActive: false } as never)
    plugins.handlers.network({ connected: false, connectionType: 'none' } as never)
    expect(seen).toEqual([])
    plugins.handlers.app({ isActive: true } as never)
    plugins.handlers.network({ connected: true, connectionType: 'wifi' } as never)
    expect(seen).toEqual(['foreground', 'network'])
    stop()
    await vi.waitFor(() => expect(Object.keys(plugins.handlers)).toEqual([]))
  })

  it('stopping before the plugins answered still removes the listeners', async () => {
    const stop = capacitorDevice.onResume(() => undefined)
    stop()
    await vi.waitFor(() => expect(Object.keys(plugins.handlers)).toEqual([]))
  })
})
