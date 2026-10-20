/**
 * The rights of this device (issue #410): the invitations pasted or opened from a link, kept to open the scopes of the published packages.
 * Together with the open key that the index publishes while the beta lasts they are the keys the app tries (`scopeKeys`). An invitation is
 * the token `bl1.<base64url JSON {s: scope, k: key, e: expiry|null}>` or the link `basketlab-live://invite#<token>`
 * (src/live_prep/package_scopes.py). Expiry is only a convention of the app: the real cut is rotating the scope on the server side.
 */
import type { ScopeKey } from './crypto'

const KEY = 'basketlab-live-rights'
const TOKEN_PREFIX = 'bl1.'
const OPEN_SCOPE = 'abierto'
/** Fired on `window` when a right is added from outside the Partidos tab (a link opened the app), so the list reads the rights again. */
export const RIGHTS_EVENT = 'basketlab-rights'

export interface Right {
  scope: string
  /** base64url of the 32-byte key of the scope. */
  key: string
  /** `YYYY-MM-DD`: from that day the app stops using it. */
  expires?: string | null
}

function fromBase64(value: string): Uint8Array {
  const bin = atob(value.replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(bin, c => c.charCodeAt(0))
}

/** The invitation of a token or a link as it was pasted; throws an error that says what to do when it is neither. */
export function parseInvite(text: string): Right {
  const token = text.trim().split('#').pop() ?? ''
  const fail = () => new Error('No es una invitación de BasketLab: pega el enlace o la clave tal como te la enviaron.')
  if (!token.startsWith(TOKEN_PREFIX) || token.length === TOKEN_PREFIX.length) throw fail()
  try {
    const payload = JSON.parse(new TextDecoder().decode(fromBase64(token.slice(TOKEN_PREFIX.length))))
    if (typeof payload.s !== 'string' || typeof payload.k !== 'string' || fromBase64(payload.k).length !== 32) throw fail()
    return { scope: payload.s, key: payload.k, expires: typeof payload.e === 'string' ? payload.e : null }
  } catch {
    throw fail()
  }
}

export function loadRights(storage: Storage = localStorage): Right[] {
  try {
    const rights = JSON.parse(storage.getItem(KEY) ?? '[]')
    return Array.isArray(rights) ? rights.filter(r => r && typeof r.scope === 'string' && typeof r.key === 'string') : []
  } catch {
    return []
  }
}

function save(rights: Right[], storage: Storage): void {
  try {
    storage.setItem(KEY, JSON.stringify(rights))
  } catch {
    /* storage unavailable: the invitation is pasted again next time */
  }
}

/** Keeps the right; one per scope (a newer invitation to the same scope replaces the old one). */
export function addRight(right: Right, storage: Storage = localStorage): void {
  save([...loadRights(storage).filter(r => r.scope !== right.scope), right], storage)
}

export function removeRight(scope: string, storage: Storage = localStorage): void {
  save(loadRights(storage).filter(r => r.scope !== scope), storage)
}

/** The rights that have not expired (the app stops using them from the expiry day). */
export function activeRights(rights: Right[], now: Date = new Date()): Right[] {
  const today = now.toISOString().slice(0, 10)
  return rights.filter(r => !r.expires || r.expires > today)
}

/** The keys to try: the open one that the index publishes (while the beta lasts) and the rights that are still valid. */
export function scopeKeys(index: { open_key?: string | null }, rights: Right[], now: Date = new Date()): ScopeKey[] {
  const keys: ScopeKey[] = index.open_key ? [{ scope: OPEN_SCOPE, key: fromBase64(index.open_key) }] : []
  return [...keys, ...activeRights(rights, now).map(r => ({ scope: r.scope, key: fromBase64(r.key) }))]
}
