/** The package password, typed once and remembered on the device (app-private storage; it only protects public FEB statistics). */
const KEY = 'basketlab-live-passphrase'

import { PackageDecryptError } from './crypto'

/** The message of a failure; for a wrong password it says how many characters were typed, so a missing letter or a stray space shows. */
export function failureText(error: unknown, typed: string): string {
  if (error instanceof PackageDecryptError) return `${error.message} Escribiste ${typed.length} caracteres.`
  return error instanceof Error ? error.message : String(error)
}

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
