/**
 * The teams "de interés" (issue #440): chosen by the user and kept ONLY on this device (never published). Ids change every season, so the name
 * is kept too and a team is recognised by either. Same pattern as `rights.ts`: a list in `localStorage`, never failing when it is blocked.
 */
const KEY = 'basketlab-live-favorites'

export interface Favorite {
  teamId: string
  name: string
}

/** `Cultural y Deportiva LEÓNESA ` -> `CULTURAL Y DEPORTIVA LEONESA`: case, accents and repeated spaces do not tell two spellings apart. */
export function normalizeName(name: string): string {
  return name.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/\s+/g, ' ').trim()
}

export function loadFavorites(storage: Storage = localStorage): Favorite[] {
  try {
    const list = JSON.parse(storage.getItem(KEY) ?? '[]')
    return Array.isArray(list) ? list.filter(f => f && typeof f.teamId === 'string' && typeof f.name === 'string').map(f => ({ teamId: f.teamId, name: f.name })) : []
  } catch {
    return []
  }
}

function save(favorites: Favorite[], storage: Storage): void {
  try {
    storage.setItem(KEY, JSON.stringify(favorites))
  } catch {
    /* storage unavailable: the stars are marked again next time */
  }
}

/** Is the team (by id, or by name when the id changed) one of the favourites? */
export function isFavorite(favorites: Favorite[], teamId: string, name: string): boolean {
  const wanted = normalizeName(name)
  return favorites.some(f => f.teamId === teamId || normalizeName(f.name) === wanted)
}

/** Keeps the team; one per id (marking it again refreshes its name). */
export function addFavorite(favorite: Favorite, storage: Storage = localStorage): void {
  save([...loadFavorites(storage).filter(f => f.teamId !== favorite.teamId), favorite], storage)
}

export function removeFavorite(teamId: string, storage: Storage = localStorage): void {
  save(loadFavorites(storage).filter(f => f.teamId !== teamId), storage)
}

/** Marks the team if it is not a favourite and unmarks it if it is (recognised by id or by name); true when it ends up marked. */
export function toggleFavorite(favorite: Favorite, storage: Storage = localStorage): boolean {
  const current = loadFavorites(storage)
  if (isFavorite(current, favorite.teamId, favorite.name)) {
    const wanted = normalizeName(favorite.name)
    save(current.filter(f => f.teamId !== favorite.teamId && normalizeName(f.name) !== wanted), storage)
    return false
  }
  save([...current, favorite], storage)
  return true
}
