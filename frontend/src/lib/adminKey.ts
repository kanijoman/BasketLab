/** Admin API key (sent as X-Admin-Key to the protected endpoints), kept per browser session. */
const KEY = 'basketlab-admin-key'

export function getAdminKey(): string {
  try {
    return sessionStorage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}

export function setAdminKey(value: string): void {
  const v = value.trim()
  try {
    if (v) sessionStorage.setItem(KEY, v)
    else sessionStorage.removeItem(KEY)
  } catch { /* storage blocked: the key just won't persist */ }
}

export function clearAdminKey(): void {
  setAdminKey('')
}

export function adminHeaders(): Record<string, string> {
  const k = getAdminKey()
  return k ? { 'X-Admin-Key': k } : {}
}
