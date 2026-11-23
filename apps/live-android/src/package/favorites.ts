/**
 * The teams "de interés" (issue #440): chosen by the user and kept ONLY on this device (never published). Ids change every season, so the name
 * is kept too and a team is recognised by either. Same pattern as `rights.ts`: a list in `localStorage`, never failing when it is blocked.
 */
import type { CompetitionInfo, RoundIndexEntry, RoundMatch } from './remote'

const KEY = 'basketlab-live-favorites'

export interface Favorite {
  teamId: string
  name: string
  /** The category the team plays in (`teamScope`); absent in a favourite saved before #1055, which is read as senior. */
  scope?: string
}

/** The category of a team (#1055): a club has the same name in every category, so «the team» is the club IN a category. Senior is one category whatever the division (a promotion
 *  keeps the favourite); a youth team is its age group; the gender tells the two branches apart. `null` when the index does not say (one from before the category existed). */
export function teamScope(info?: Pick<CompetitionInfo, 'category' | 'age_group' | 'gender'> | null): string | null {
  if (!info?.category) return null
  const base = info.category === 'formacion' ? info.age_group || 'formacion' : 'senior'
  return `${base}:${info.gender ?? ''}`
}

const isSenior = (scope: string) => scope.startsWith('senior:')

/** `Cultural y Deportiva LEÓNESA ` -> `CULTURAL Y DEPORTIVA LEONESA`: case, accents and repeated spaces do not tell two spellings apart. */
export function normalizeName(name: string): string {
  return name.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/\s+/g, ' ').trim()
}

export function loadFavorites(storage: Storage = localStorage): Favorite[] {
  try {
    const list = JSON.parse(storage.getItem(KEY) ?? '[]')
    return Array.isArray(list)
      ? list.filter(f => f && typeof f.teamId === 'string' && typeof f.name === 'string').map(f => ({ teamId: f.teamId, name: f.name, ...(typeof f.scope === 'string' ? { scope: f.scope } : {}) }))
      : []
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

/** Does this favourite name the team? The id is the same team in any category; the name stands for it across seasons (ids change), but only inside the same category (#1055): the
 *  favourite of a club's senior team does not mark its cadete team. A favourite from before the category existed is read as senior; a match whose category is not known (an old
 *  index) is told by the name alone, as before. */
function isTeam(f: Favorite, teamId: string, name: string, scope: string | null): boolean {
  if (f.teamId === teamId) return true
  if (normalizeName(f.name) !== normalizeName(name)) return false
  if (scope === null) return true
  return f.scope ? f.scope === scope : isSenior(scope)
}

/** Is the team (by id, or by name in its category when the id changed) one of the favourites? */
export function isFavorite(favorites: Favorite[], teamId: string, name: string, scope: string | null = null): boolean {
  return favorites.some(f => isTeam(f, teamId, name, scope))
}

/** Does a favourite play this match, on either side (the category being the one of the round's competition)? */
export function hasFavorite(round: Pick<RoundIndexEntry, 'competition'>, match: RoundMatch, favorites: Favorite[]): boolean {
  const scope = teamScope(round.competition)
  return isFavorite(favorites, match.home.id, match.home.name, scope) || isFavorite(favorites, match.away.id, match.away.name, scope)
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
  const scope = favorite.scope ?? null
  if (isFavorite(current, favorite.teamId, favorite.name, scope)) {
    save(current.filter(f => !isTeam(f, favorite.teamId, favorite.name, scope)), storage)
    return false
  }
  save([...current, favorite], storage)
  return true
}
