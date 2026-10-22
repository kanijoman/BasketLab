/** The next match of each team "de interés" among the published rounds (issue #478): what «Próximos partidos» shows for them. */
import { isFavorite, type Favorite } from './favorites'
import type { RoundIndexEntry, RoundMatch } from './remote'

/** A match counts as the next one until this long after its start (it may be on). */
const STILL_ON_MS = 2 * 60 * 60 * 1000

export interface NextMatch {
  favorite: Favorite
  round: RoundIndexEntry
  match: RoundMatch
  /** The side of the favourite: the team whose point of view is followed. */
  ownId: string
  rival: { id: string; name: string }
}

const startOf = (m: RoundMatch): number | null => {
  const t = m.start ? new Date(m.start).getTime() : NaN
  return Number.isNaN(t) ? null : t
}

/** For each favourite, its nearest match that has not ended; the lines come in date order, the ones without a date last. */
export function nextMatchesOfFavorites(rounds: RoundIndexEntry[], favorites: Favorite[], now: Date = new Date()): NextMatch[] {
  const limit = now.getTime() - STILL_ON_MS
  const found: NextMatch[] = []
  for (const favorite of favorites) {
    let best: NextMatch | null = null
    for (const round of rounds) {
      for (const match of round.matches) {
        const home = isFavorite([favorite], match.home.id, match.home.name)
        const away = !home && isFavorite([favorite], match.away.id, match.away.name)
        const at = startOf(match)
        if (!(home || away) || (at !== null && at < limit)) continue
        const candidate: NextMatch = { favorite, round, match, ownId: home ? match.home.id : match.away.id, rival: home ? match.away : match.home }
        const bestAt = best ? startOf(best.match) : null
        if (!best || (at !== null && (bestAt === null || at < bestAt))) best = candidate
      }
    }
    if (best) found.push(best)
  }
  return found.sort((a, b) => (startOf(a.match) ?? Infinity) - (startOf(b.match) ?? Infinity))
}
