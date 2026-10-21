/**
 * Filters of the matches list of the Partidos tab (issue #440): by competition, group, team or text, and only the teams "de interés".
 * The labels come from the competition data of the index (publisher, #438); an index that has none falls back to the name of the collection.
 * The chosen filters are remembered on the device (same pattern as `useTab.ts`).
 */
import { isFavorite, normalizeName, type Favorite } from './favorites'
import { competitionLabel, type RoundIndexEntry, type RoundMatch } from './remote'

const KEY = 'basketlab-live-filters'

export interface RoundFilters {
  /** `''`: every competition. */
  competition: string
  /** `''`: every group of the competition. */
  group: string
  text: string
  onlyFavorites: boolean
}

export const NO_FILTERS: RoundFilters = { competition: '', group: '', text: '', onlyFavorites: false }

export interface CompetitionOf {
  name: string
  group: string
  label: string
}

export function competitionOf(round: RoundIndexEntry): CompetitionOf {
  const info = round.competition
  if (info) return { name: info.competition, group: info.group, label: info.label || (info.group ? `${info.competition} · ${info.group}` : info.competition) }
  const label = competitionLabel(round.collection)
  return { name: label, group: '', label }
}

const hasFavorite = (match: RoundMatch, favorites: Favorite[]) =>
  isFavorite(favorites, match.home.id, match.home.name) || isFavorite(favorites, match.away.id, match.away.name)

/** The matches that pass the filters; a round left without matches is dropped. Nothing given is modified. */
export function filterRounds(rounds: RoundIndexEntry[], filters: RoundFilters, favorites: Favorite[]): RoundIndexEntry[] {
  const text = normalizeName(filters.text)
  return rounds.flatMap(round => {
    const c = competitionOf(round)
    if ((filters.competition && c.name !== filters.competition) || (filters.group && c.group !== filters.group)) return []
    const matches = round.matches.filter(m =>
      (!filters.onlyFavorites || hasFavorite(m, favorites)) &&
      (!text || [m.home.name, m.away.name, c.label].some(part => normalizeName(part).includes(text))))
    return matches.length > 0 ? [{ ...round, matches }] : []
  })
}

/** The competitions to choose, and the groups of the chosen one (none while no competition is chosen). */
export function optionsOf(rounds: RoundIndexEntry[], competition: string): { competitions: string[]; groups: string[] } {
  const unique = (values: string[]) => Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b))
  const all = rounds.map(competitionOf)
  return { competitions: unique(all.map(c => c.name)), groups: competition ? unique(all.filter(c => c.name === competition).map(c => c.group)) : [] }
}

export function loadFilters(storage: Storage = localStorage): RoundFilters {
  try {
    const raw = JSON.parse(storage.getItem(KEY) ?? '{}')
    const str = (v: unknown) => (typeof v === 'string' ? v : '')
    return { competition: str(raw.competition), group: str(raw.group), text: str(raw.text), onlyFavorites: raw.onlyFavorites === true }
  } catch {
    return NO_FILTERS
  }
}

export function saveFilters(filters: RoundFilters, storage: Storage = localStorage): void {
  try {
    storage.setItem(KEY, JSON.stringify(filters))
  } catch {
    /* blocked storage: the filters are chosen again next time, it is only a convenience */
  }
}
