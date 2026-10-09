/** The package password, typed once and remembered on the device (app-private storage; it only protects public FEB statistics). */
const KEY = 'basketlab-live-passphrase'

export function loadPassphrase(storage: Storage = localStorage): string {
  try {
    return storage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}

export function savePassphrase(value: string, storage: Storage = localStorage): void {
  try {
    storage.setItem(KEY, value)
  } catch {
    /* storage unavailable: the user types it again next time */
  }
}

export function clearPassphrase(storage: Storage = localStorage): void {
  try {
    storage.removeItem(KEY)
  } catch {
    /* nothing to clear */
  }
}
