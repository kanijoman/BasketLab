// The list of competitions on the device (issue #705): `CollectionService.list_available` from the manifest of the publication. The database lists its collections and parses the
// components out of each name; the manifest has one entry per published competition (name, league, games), so the list is the same names with the same components, sorted the same way.
// Parity: `collections.test.ts` against `tests/local_vectors/collections.json` (the real collection names of a working copy).
import type { CollectionInfo } from '@/api/client'

const YEAR = /^\d{4}$/
const GROUP = /^[A-Z0-9]{1,2}$/i
const FBCYL_PREFIX = /^FBCYL_/i

export type League = 'FEB' | 'FBCYL'

/** What the manifest says of a competition. */
export interface PublishedCollection {
  collection: string
  league: 'feb' | 'fbcyl'
  games: number
  category?: 'senior' | 'formacion'
  age_group?: 'U14' | 'U16' | 'U18'
  competition_label?: string
  group_label?: string
}

/** Best-effort parsing of the competition, the season and the group of a collection name (`_parse_components`): FBCYL `FBCYL_{competition}_{season}`, FEB a slug with the year(s) of the season. */
export function parseComponents(name: string, league: League): { competition: string; season: string; group: string } {
  if (league === 'FBCYL') {
    const rest = name.replace(FBCYL_PREFIX, '')
    const cut = rest.indexOf('_')
    return cut < 0 ? { competition: rest, season: '', group: '' } : { competition: rest.slice(0, cut), season: rest.slice(cut + 1).replace(/_/g, ' '), group: '' }
  }
  const parts = name.split('_')
  const yearAt = parts.findIndex(p => YEAR.test(p))
  if (yearAt < 0) return { competition: name, season: '', group: '' }
  const remainder = parts.slice(yearAt)
  // a short last token (A, B, 1A…) is the group; a longer phase name (ELIMINATORIAS, FASE_ASCENSO) stays in the season
  const hasGroup = remainder.length > 1 && GROUP.test(remainder[remainder.length - 1])
  return {
    competition: parts.slice(0, yearAt).join('_'),
    season: (hasGroup ? remainder.slice(0, -1) : remainder).join('_'),
    group: hasGroup ? remainder[remainder.length - 1] : '',
  }
}

const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0)             // code units, as Python compares strings (not the locale: accents and case differ)

/** The competitions of the publication as the API lists them: league, then season (the newest first), competition and group. */
export function collectionList(published: PublishedCollection[]): CollectionInfo[] {
  const rows = published.map((entry): CollectionInfo => ({
    name: entry.collection, league: entry.league === 'fbcyl' ? 'FBCYL' : 'FEB', ...parseComponents(entry.collection, entry.league === 'fbcyl' ? 'FBCYL' : 'FEB'), game_count: entry.games,
    ...(entry.category ? { category: entry.category } : {}), ...(entry.age_group ? { age_group: entry.age_group } : {}), ...(entry.competition_label ? { competition_label: entry.competition_label } : {}), ...(entry.group_label ? { group_label: entry.group_label } : {}),
  }))
  return rows.sort((a, b) => compare(a.league, b.league) || compare('-' + a.season, '-' + b.season) || compare(a.competition, b.competition) || compare(a.group, b.group))
}
