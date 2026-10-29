// Invitations as links (issue #639): `<page>#invite=bl1.<token>`. Opening one adds the right to this browser (`@live-package/rights`, the same format the
// live app uses) and takes the key out of the address bar, so it is not left in the history, in a screenshot or in what the reader copies and shares.
import { addRight, parseInvite, type Right } from '@live-package/rights'

const PARAM = 'invite='

/** The invitation of what a reader pastes: the whole link of the web (`...#invite=bl1.xxx`), the app's link or the bare token (`bl1.xxx`). */
export function parseWebInvite(text: string): Right {
  const found = text.match(/invite=([^\s&]+)/)
  return parseInvite(found ? found[1] : text)
}

/** The invitation in the address, kept as a right and removed from it; `null` when there is none or it does not work (nothing is added, nothing throws). */
export function consumeInviteFromUrl(): Right | null {
  const hash = window.location.hash
  if (!hash.startsWith(`#${PARAM}`)) return null
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
  try {
    const right = parseWebInvite(hash)
    addRight(right)
    return right
  } catch {
    return null
  }
}
