/**
 * The tablet side of the live mode: keep the screen on while the connection runs (issue #219) and tell when the app comes back
 * to the foreground or the network is back (issue #220). The Capacitor plugins hide behind this small interface so the live mode
 * can be tested without a device; on the web build the plugins fall back to the browser (Wake Lock, online events).
 */
import { KeepAwake } from '@capacitor-community/keep-awake'
import { App } from '@capacitor/app'
import { Network } from '@capacitor/network'

export type ResumeReason = 'foreground' | 'network'

export interface Device {
  /** Keeps the screen on; false when the device cannot (the staff is told). */
  keepAwake(): Promise<boolean>
  allowSleep(): Promise<void>
  /** Calls back when the app returns to the foreground or the network comes back; returns the function that stops listening. */
  onResume(callback: (reason: ResumeReason) => void): () => void
}

type Handle = { remove: () => Promise<void> }

export const capacitorDevice: Device = {
  async keepAwake() {
    try { await KeepAwake.keepAwake(); return true } catch { return false }
  },

  async allowSleep() {
    try { await KeepAwake.allowSleep() } catch { /* nothing to release */ }
  },

  onResume(callback) {
    let stopped = false
    const handles: Promise<Handle | null>[] = [
      App.addListener('appStateChange', ({ isActive }) => { if (isActive && !stopped) callback('foreground') }).catch(() => null),
      Network.addListener('networkStatusChange', ({ connected }) => { if (connected && !stopped) callback('network') }).catch(() => null),
    ]
    return () => {
      stopped = true
      for (const handle of handles) void handle.then(h => h?.remove())
    }
  },
}
