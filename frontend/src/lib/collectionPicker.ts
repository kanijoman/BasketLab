/**
 * Choosing a competition by levels (issue #761): ámbito (the league of the data: FEB, FBCYL, and whatever federation is added) → temporada → competición → grupo.
 * Each level only offers what the previous ones allow; a choice that does not exist at the new level falls back to the default (the latest season, the first competition and group),
 * so the four levels always name one collection that exists. Pure: the home page and the header selector share it.
 */
import type { CollectionInfo } from '@/api/client'

export interface Selection { ambito?: string; season?: string; competition?: string; group?: string }

export interface Picker {
  ambitos: string[]
  seasons: string[]
  competitions: string[]
  groups: string[]
  selection: Required<Selection>
  collection: CollectionInfo | null
}

const FIRST = ['FEB', 'FBCYL']

const unique = (values: string[]) => [...new Set(values)]
const resolve = (options: string[], wanted: string | undefined) => (wanted !== undefined && options.includes(wanted) ? wanted : options[0] ?? '')

/** FEB and FBCYL first, the other ámbitos after them in alphabetical order. */
function byAmbito(a: string, b: string): number {
  const ia = FIRST.indexOf(a), ib = FIRST.indexOf(b)
  if (ia >= 0 || ib >= 0) return (ia < 0 ? FIRST.length : ia) - (ib < 0 ? FIRST.length : ib)
  return a.localeCompare(b)
}

export function pickCollection(list: CollectionInfo[], wanted: Selection): Picker {
  const ambitos = unique(list.map(c => c.league)).sort(byAmbito)
  const ambito = resolve(ambitos, wanted.ambito)
  const inAmbito = list.filter(c => c.league === ambito)
  const seasons = unique(inAmbito.map(c => c.season)).sort((a, b) => b.localeCompare(a))
  const season = resolve(seasons, wanted.season)
  const inSeason = inAmbito.filter(c => c.season === season)
  const competitions = unique(inSeason.map(c => c.competition)).sort((a, b) => a.localeCompare(b))
  const competition = resolve(competitions, wanted.competition)
  const inCompetition = inSeason.filter(c => c.competition === competition)
  const groups = unique(inCompetition.map(c => c.group ?? '')).sort((a, b) => a.localeCompare(b))
  const group = resolve(groups, wanted.group)
  const collection = inCompetition.find(c => (c.group ?? '') === group) ?? null
  return { ambitos, seasons, competitions, groups, selection: { ambito, season, competition, group }, collection }
}

/** The levels of a collection (the header starts on the current one). */
export function selectionOf(c: CollectionInfo): Required<Selection> {
  return { ambito: c.league, season: c.season, competition: c.competition, group: c.group ?? '' }
}
