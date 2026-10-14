/** A short log of what happened to the match on this device (issue #309): restarts, jumps and starts of the app, with their time.
 *  When the match "goes back to the start by itself" it tells a tap of the user from the system restarting the app: the startup
 *  notes if the previous session was alive a few seconds before (a heartbeat in the storage). The storage can be blocked: then
 *  there is just no log. */

export const LOG_KEY = 'basketlab-live-session-log'
export const BEAT_KEY = 'basketlab-live-beat'
export const MAX_EVENTS = 30
export const BEAT_EVERY_MS = 5_000
/** A start this soon after the last heartbeat is a restart nobody asked for (a normal close and reopen takes longer). */
export const RESTART_WITHIN_MS = 120_000

export interface SessionEvent {
  t: number
  text: string
}

function read(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}

function write(key: string, value: string): void {
  try { localStorage.setItem(key, value) } catch { /* blocked storage: no log */ }
}

export function readSession(): SessionEvent[] {
  try {
    const parsed: unknown = JSON.parse(read(LOG_KEY) ?? '[]')
    return Array.isArray(parsed)
      ? parsed.filter((e): e is SessionEvent => typeof e?.t === 'number' && typeof e?.text === 'string')
      : []
  } catch {
    return []
  }
}

export function recordSession(text: string, now: number = Date.now()): void {
  write(LOG_KEY, JSON.stringify([...readSession(), { t: now, text }].slice(-MAX_EVENTS)))
}

export function beat(now: number = Date.now()): void {
  write(BEAT_KEY, String(now))
}

/** Log the start of the app, saying when the previous session was last alive if it was only seconds ago. */
export function markStartup(now: number = Date.now()): void {
  const last = Number(read(BEAT_KEY))
  const ago = Number.isFinite(last) && last > 0 ? now - last : null
  if (ago !== null && ago >= 0 && ago <= RESTART_WITHIN_MS) {
    recordSession(`Arranque de la app: la sesión anterior estaba activa hace ${Math.round(ago / 1000)} s (reinicio no pedido)`, now)
  } else {
    recordSession('Arranque de la app', now)
  }
  beat(now)
}

export function formatSession(e: SessionEvent): string {
  const d = new Date(e.t)
  const day = d.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' })
  const time = d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  return `${day} ${time} · ${e.text}`
}
