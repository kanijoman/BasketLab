/** Recently opened collections (localStorage) shown at the top of the home page. */

const RECENTS_KEY = 'basketlab-recent-collections'
const MAX_RECENTS = 5

export interface RecentCollection {
  name: string
  label: string
  isFbcyl: boolean
  accessedAt: string
}

export function loadRecents(): RecentCollection[] {
  try {
    return JSON.parse(localStorage.getItem(RECENTS_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function saveRecent(name: string, isFbcyl: boolean) {
  const recents = loadRecents().filter(r => r.name !== name)
  const parts = name.split('_')
  const label = parts.length > 1 ? `${parts[0]} · ${parts.slice(1).join(' · ')}` : name
  recents.unshift({ name, label, isFbcyl, accessedAt: new Date().toISOString() })
  try {
    localStorage.setItem(RECENTS_KEY, JSON.stringify(recents.slice(0, MAX_RECENTS)))
  } catch { /* ignore */ }
}

/** Recent collections that still exist in the database (a dropped collection must not linger in the list). */
export function pruneRecents(recents: RecentCollection[], existing: { name: string }[]): RecentCollection[] {
  const names = new Set(existing.map(c => c.name))
  return recents.filter(r => names.has(r.name))
}

export function saveRecents(recents: RecentCollection[]) {
  try {
    localStorage.setItem(RECENTS_KEY, JSON.stringify(recents.slice(0, MAX_RECENTS)))
  } catch { /* ignore */ }
}
