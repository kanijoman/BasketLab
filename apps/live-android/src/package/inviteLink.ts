/**
 * Invitation links (issue #410): `basketlab-live://invite#<token>` opens the app (intent filter in AndroidManifest.xml) and the token becomes a
 * right of the device (see rights.ts). Capacitor's App plugin delivers the link that opens a running app (`appUrlOpen`) and the one that
 * launched it (`getLaunchUrl`); on the web build both fail and nothing happens (the invitation is pasted instead).
 */
import { App } from '@capacitor/app'
import { RIGHTS_EVENT, addRight, parseInvite } from './rights'

export const INVITE_URL_PREFIX = 'basketlab-live://invite'

export type InviteResult = { ok: true; scope: string } | { ok: false; message: string }

/** Keeps the right of an invitation link; null when the url is not an invitation link at all. */
export function acceptInviteUrl(url: string): InviteResult | null {
  if (!url.startsWith(INVITE_URL_PREFIX)) return null
  try {
    const right = parseInvite(url)
    addRight(right)
    return { ok: true, scope: right.scope }
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : String(e) }
  }
}

/** Listens for invitation links; returns the function that stops listening. */
export function listenInviteLinks(onResult: (result: InviteResult) => void): () => void {
  let stopped = false
  const handle = (url: string | undefined) => {
    const result = url ? acceptInviteUrl(url) : null
    if (!result || stopped) return
    window.dispatchEvent(new Event(RIGHTS_EVENT))
    onResult(result)
  }
  const listener = Promise.resolve().then(() => App.addListener('appUrlOpen', ({ url }) => handle(url))).catch(() => null)
  void Promise.resolve().then(() => App.getLaunchUrl()).then(launch => handle(launch?.url)).catch(() => undefined)
  return () => {
    stopped = true
    void listener.then(h => h?.remove())
  }
}
