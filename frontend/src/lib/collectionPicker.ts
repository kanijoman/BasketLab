/**
 * Choosing a competition by levels (issue #761): ámbito (the league of the data: FEB, FBCYL, and whatever federation is added) → temporada (always the two years: 2026/2027; a name with a single year gives the year the season starts in) → competición
 * (its name: PRIMERA FEB, LF ENDESA…) → grupo (what tells the collections of a competition apart: the phase and the group, «Liga Regular A», «Play-offs 1/2 Final»).
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

const YEAR = /^\d{4}$/
/** A competition with a single group says «Único»: nothing to show. */
const ONLY_GROUP = /^[uú]nico$/i

/**
 * FBCYL names its competitions with a code (`FBCYL_1ª_…`) that says nothing to a person: the names people use, for the codes known so far. A code that is not here is shown as the data
 * gives it; add the new ones as competitions are published (FEB's names are already readable).
 */
const FBCYL_NAMES: Record<string, string> = { '1ª': '1ª División Femenina' }

const words = (text: string) => text.split(/[_\s]+/).filter(Boolean)
/** «1_8» is a fraction of the draw: 1/8. */
const fractions = (text: string) => text.replace(/(\d)\s(\d)/g, '$1/$2')

const competitionName = (c: CollectionInfo): string => {
  const name = words(c.competition ?? '').join(' ')
  return c.league === 'FBCYL' ? FBCYL_NAMES[name] ?? name : name
}

/** The four levels of a collection as the selectors show them, read from what the name gives (`localdata/collections.parseComponents`): the years of its season, the name of its competition and the rest (phase and group). */
export function levelsOf(c: CollectionInfo): Required<Selection> {
  const tokens = words(c.season ?? '')
  const years = [...new Set(tokens.filter(t => YEAR.test(t)))].sort()
  const phase = fractions(tokens.filter(t => !YEAR.test(t) && !ONLY_GROUP.test(t)).join(' '))
  const group = c.group && !ONLY_GROUP.test(c.group) ? c.group : ''
  return {
    ambito: c.league,
    season: years.length === 1 ? `${years[0]}/${Number(years[0]) + 1}` : years.join('/'),
    competition: competitionName(c),
    group: [phase, group].filter(Boolean).join(' '),
  }
}

/** The regular league first, then the other phases in alphabetical order. */
const byGroup = (a: string, b: string) => Number(!/^liga/i.test(a)) - Number(!/^liga/i.test(b)) || a.localeCompare(b)

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
  const all = list.map(c => ({ c, l: levelsOf(c) }))
  const ambitos = unique(all.map(x => x.l.ambito)).sort(byAmbito)
  const ambito = resolve(ambitos, wanted.ambito)
  const inAmbito = all.filter(x => x.l.ambito === ambito)
  const seasons = unique(inAmbito.map(x => x.l.season)).sort((a, b) => b.localeCompare(a))
  const season = resolve(seasons, wanted.season)
  const inSeason = inAmbito.filter(x => x.l.season === season)
  const competitions = unique(inSeason.map(x => x.l.competition)).sort((a, b) => a.localeCompare(b))
  const competition = resolve(competitions, wanted.competition)
  const inCompetition = inSeason.filter(x => x.l.competition === competition)
  const groups = unique(inCompetition.map(x => x.l.group)).sort(byGroup)
  const group = resolve(groups, wanted.group)
  const collection = inCompetition.find(x => x.l.group === group)?.c ?? null
  return { ambitos, seasons, competitions, groups, selection: { ambito, season, competition, group }, collection }
}

/** The levels of a collection (the header starts on the current one). */
export const selectionOf = levelsOf

/** «SEGUNDA FEB 2026/2027 · Liga Regular B»: what a collection is called on the home page. */
export function collectionLabel(c: CollectionInfo): string {
  const { competition, season, group } = levelsOf(c)
  return [`${competition} ${season}`.trim(), group].filter(Boolean).join(' · ')
}
