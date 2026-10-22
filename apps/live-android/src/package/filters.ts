/**
 * Filters of the matches list of the Partidos tab (issues #440, #474): by league (FEB / FBCYL, once there is more than one), competition, group,
 * team (a list of the teams of the chosen competition) and only the teams "de interés".
 * The labels come from the competition data of the index (publisher, #438); an index that has none falls back to the name of the collection.
 * The chosen filters are remembered on the device (same pattern as `useTab.ts`).
 */
import { isFavorite, type Favorite } from './favorites'
import { competitionLabel, type RoundIndexEntry, type RoundMatch } from './remote'

const KEY = 'basketlab-live-filters'

export interface RoundFilters {
  /** `''`: every league. */
  league: string
  /** `''`: every competition. */
  competition: string
  /** `''`: every group of the competition. */
  group: string
  /** Id of a team of the chosen competition; `''`: every team. */
  team: string
  onlyFavorites: boolean
}

export const NO_FILTERS: RoundFilters = { league: '', competition: '', group: '', team: '', onlyFavorites: false }

export interface CompetitionOf {
  name: string
  group: string
  label: string
}

export interface TeamOption {
  id: string
  name: string
}

export function competitionOf(round: RoundIndexEntry): CompetitionOf {
  const info = round.competition
  if (info) return { name: info.competition, group: info.group, label: info.label || (info.group ? `${info.competition} · ${info.group}` : info.competition) }
  const label = competitionLabel(round.collection)
  return { name: label, group: '', label }
}

/** `FEB` or `FBCYL`: what the publisher says, else the prefix of the collection (the FBCYL ones start with `FBCYL_`). */
export function leagueOf(round: RoundIndexEntry): string {
  const said = round.competition?.league
  if (said) return said
  return /^FBCYL_/i.test(round.collection) ? 'FBCYL' : 'FEB'
}

const hasFavorite = (match: RoundMatch, favorites: Favorite[]) =>
  isFavorite(favorites, match.home.id, match.home.name) || isFavorite(favorites, match.away.id, match.away.name)

const inScope = (round: RoundIndexEntry, filters: RoundFilters) => {
  const c = competitionOf(round)
  return (!filters.league || leagueOf(round) === filters.league) && (!filters.competition || c.name === filters.competition) && (!filters.group || c.group === filters.group)
}

/** The matches that pass the filters; a round left without matches is dropped. Nothing given is modified. */
export function filterRounds(rounds: RoundIndexEntry[], filters: RoundFilters, favorites: Favorite[]): RoundIndexEntry[] {
  return rounds.flatMap(round => {
    if (!inScope(round, filters)) return []
    const matches = round.matches.filter(m =>
      (!filters.onlyFavorites || hasFavorite(m, favorites)) && (!filters.team || m.home.id === filters.team || m.away.id === filters.team))
    return matches.length > 0 ? [{ ...round, matches }] : []
  })
}

export interface FilterOptions {
  leagues: string[]
  competitions: string[]
  groups: string[]
  teams: TeamOption[]
}

/** What each selector offers: the leagues (only when there is more than one), the competitions of the league, the groups of the competition and the teams of the
 *  competition and group (none while no competition is chosen). */
export function optionsOf(rounds: RoundIndexEntry[], filters: RoundFilters): FilterOptions {
  const unique = (values: string[]) => Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b))
  const leagues = unique(rounds.map(leagueOf))
  const ofLeague = rounds.filter(r => !filters.league || leagueOf(r) === filters.league)
  const ofCompetition = filters.competition ? ofLeague.filter(r => competitionOf(r).name === filters.competition) : []
  const scoped = ofCompetition.filter(r => !filters.group || competitionOf(r).group === filters.group)
  const teams = new Map<string, string>()
  for (const r of scoped) for (const m of r.matches) for (const t of [m.home, m.away]) if (!teams.has(t.id)) teams.set(t.id, t.name.trim())
  return {
    leagues: leagues.length > 1 ? leagues : [],
    competitions: unique(ofLeague.map(r => competitionOf(r).name)),
    groups: unique(ofCompetition.map(r => competitionOf(r).group)),
    teams: Array.from(teams, ([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, 'es')),
  }
}

export function loadFilters(storage: Storage = localStorage): RoundFilters {
  try {
    const raw = JSON.parse(storage.getItem(KEY) ?? '{}')
    const str = (v: unknown) => (typeof v === 'string' ? v : '')
    return { league: str(raw.league), competition: str(raw.competition), group: str(raw.group), team: str(raw.team), onlyFavorites: raw.onlyFavorites === true }
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
