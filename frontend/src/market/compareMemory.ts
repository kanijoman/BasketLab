// The comparison that Talent remembers while the tab is open (#1007): going from the comparator to the search and back does not lose the players. In `sessionStorage` (per tab, gone with it), always inside
// try/catch (blocked storage must not break a page). The people of the address are still the truth of the comparator: this only fills the link of the main navigation.
import { parseCompare } from './compare'

const KEY = 'talent-compare'

/** The remembered players, in order (nothing if there is none or the value is damaged). */
export function recallCompare(): string[] {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? '[]')
    return Array.isArray(value) ? parseCompare(value.filter((x): x is string => typeof x === 'string').join(',')) : []
  } catch { return [] }
}

/** Remember the players of the comparison (an empty list forgets them). */
export function rememberCompare(ids: string[]): void {
  try { sessionStorage.setItem(KEY, JSON.stringify(ids)) } catch { /* blocked storage: only this page */ }
}

/** The address of the comparator, with the remembered players when there are some. */
export function compareHref(): string {
  const ids = recallCompare()
  return ids.length ? `/comparar?j=${encodeURIComponent(ids.join(','))}` : '/comparar'
}
