/** The next match of each team "de interés" among the published rounds (issue #478): what «Próximos partidos» shows for them. */
import { isFavorite, type Favorite } from './favorites'
import { inScope, type RoundFilters } from './filters'
import { sidesOf, type RoundIndexEntry, type RoundMatch } from './remote'

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


export interface UpcomingMatch {
  round: RoundIndexEntry
  match: RoundMatch
  /** The sides it is followed as: the favourite (both when two favourites play each other, to choose), else any side the package offers. */
  sides: string[]
}

/** The matches to follow (issues #510, #511): the next match of each team that passes the filters (the chosen team alone), each match once.
 *  Without a team chosen, the matches of the teams of interest come first; then by date, the ones without a date last. */
export function nextMatchList(rounds: RoundIndexEntry[], filters: RoundFilters, favorites: Favorite[], now: Date = new Date()): UpcomingMatch[] {
  const limit = now.getTime() - STILL_ON_MS
  const best = new Map<string, { round: RoundIndexEntry; match: RoundMatch }>()    // team id -> its next match
  for (const round of rounds) {
    if (!inScope(round, filters)) continue
    for (const match of round.matches) {
      const at = startOf(match)
      if (at !== null && at < limit) continue
      for (const team of [match.home, match.away]) {
        if (filters.team && team.id !== filters.team) continue
        const current = best.get(team.id)
        const currentAt = current ? startOf(current.match) : null
        if (!current || (at !== null && (currentAt === null || at < currentAt))) best.set(team.id, { round, match })
      }
    }
  }
  const unique = new Map<string, { round: RoundIndexEntry; match: RoundMatch }>()
  for (const entry of best.values()) unique.set(entry.match.code, entry)
  const favoriteSides = (m: RoundMatch) => [m.home, m.away].filter(t => isFavorite(favorites, t.id, t.name)).map(t => t.id)
  const found = Array.from(unique.values()).map(({ round, match }) => {
    const mine = favoriteSides(match)
    const offered = sidesOf(match)
    return { round, match, sides: mine.length ? offered.filter(id => mine.includes(id)).concat(mine.filter(id => !offered.includes(id))) : offered }
  })
  const rank = (u: UpcomingMatch) => (!filters.team && favoriteSides(u.match).length > 0 ? 0 : 1)
  return found.sort((a, b) => rank(a) - rank(b) || (startOf(a.match) ?? Infinity) - (startOf(b.match) ?? Infinity))
}
