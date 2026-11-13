/**
 * Choosing a competition by levels (issue #761): ámbito (the league of the data: FEB, FBCYL, and whatever federation is added) → categoría (Sénior or Formación, from the catalogue, #914) → temporada (always the two years: 2026/2027; a name with a single year gives the year the season starts in) → competición
 * (its name: PRIMERA FEB, LF ENDESA…) → grupo (what tells the collections of a competition apart: the phase and the group, «Liga Regular A», «Play-offs 1/2 Final»).
 * Each level only offers what the previous ones allow; a choice that does not exist at the new level falls back to the default (the latest season, the first competition and group),
 * so the five levels always name one collection that exists. Pure: the home page and the header selector share it.
 */
import type { CollectionInfo } from '@/api/client'

export interface Selection { ambito?: string; category?: string; season?: string; competition?: string; group?: string }

export interface Picker {
  ambitos: string[]
  categories: string[]
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
/** «1 2» is a round of the draw, 1/2 (only a numerator of 1: «1-8 1 2 Final» is the places 1-8, semifinal). */
const fractions = (text: string) => text.replace(/\b1\s(2|4|8|16|32)\b/g, '1/$1')
/** The phase and the group of FEB often say the same thing twice («3º-4º 3º-4º», «1/2 1/2 Final»): a run of words that is immediately repeated counts once. */
function withoutRepeats(text: string): string {
  let list = text.split(' ').filter(Boolean)
  for (let size = Math.floor(list.length / 2); size >= 1; size--) {
    for (let i = 0; i + 2 * size <= list.length; i++) {
      if (list.slice(i, i + size).join(' ') === list.slice(i + size, i + 2 * size).join(' ')) { list = [...list.slice(0, i + size), ...list.slice(i + 2 * size)]; i-- }
    }
  }
  return list.join(' ')
}

const competitionName = (c: CollectionInfo): string => {
  const name = words(c.competition ?? '').join(' ')
  return c.competition_label ?? (c.league === 'FBCYL' ? FBCYL_NAMES[name] ?? name : name)
}

/** The categories, Sénior first: a collection the manifest says nothing of is senior (older publications and the API do not have the field). */
const CATEGORIES = ['Sénior', 'Formación']
const categoryOf = (c: CollectionInfo) => (c.category === 'formacion' ? 'Formación' : 'Sénior')

/** The five levels of a collection as the selectors show them, read from what the name gives (`localdata/collections.parseComponents`): the years of its season, the name of its competition and the rest (phase and group). */
export function levelsOf(c: CollectionInfo): Required<Selection> {
  const tokens = words(c.season ?? '')
  const years = [...new Set(tokens.filter(t => YEAR.test(t)))].sort()
  const phase = fractions(tokens.filter(t => !YEAR.test(t) && !ONLY_GROUP.test(t)).join(' '))
  const group = c.group && !ONLY_GROUP.test(c.group) ? c.group : ''
  return {
    ambito: c.league,
    category: categoryOf(c),
    season: years.length === 1 ? `${years[0]}/${Number(years[0]) + 1}` : years.join('/'),
    competition: competitionName(c),
    group: withoutRepeats([phase, group].filter(Boolean).join(' ')),
  }
}

/**
 * The order of the groups of a competition: the first phase (regular league, groups), the second phase, the eliminatory rounds (by the places they play for, then the draw from the
 * biggest to the final), the classification games (3º-4º, 5º-6º…) and what is left. «Final» alone is the last round; a fraction (1/8, 1/4, 1/2) is a round of the draw.
 */
const FIRST_PHASE = /^(liga regular|primera fase|1[ªa] fase|fase de grupos|fase grupos|fase-grupo)/i
const SECOND_PHASE = /^2[ªa]\.? fase/i
const CLASSIFICATION = /^(?:\D*?)(\d+)\s*º\s*-\s*\d+\s*º/
const ELIMINATION = /play-?offs?|eliminatorias|fase final|c sm reina|supercopa|permanencia|play-?out|\bfinal\b/i
const FRACTION = /\s*\b1\/(\d+)\b/

type GroupKey = [number, number, string, number, string]
/** An elimination round: the places it plays for (1-8, 9-16), the text before the round (so «C SM Reina» and «Play-Offs» do not interleave), then the draw from the biggest to the final. A final between named seeds («1ªE-1ªO Final») goes last. */
function eliminationKey(label: string): GroupKey {
  const fraction = FRACTION.exec(label)
  const prefix = (fraction ? label.slice(0, fraction.index) : label.replace(/\s*final$/i, '')).trim()
  const places = /(?<![\d/])(\d+)-\d+(?!\s*º)/.exec(label)
  return [2, places ? Number(places[1]) : 0, /^\d/.test(prefix) ? '￿' : prefix, -(fraction ? Number(fraction[1]) : 1), label]
}

function groupKey(label: string): GroupKey {
  if (FIRST_PHASE.test(label)) return [0, 0, '', 0, label]
  if (SECOND_PHASE.test(label)) return [1, 0, '', 0, label]
  const classification = CLASSIFICATION.exec(label)
  if (classification && !ELIMINATION.test(label)) return [3, Number(classification[1]), '', 0, label]
  if (ELIMINATION.test(label)) return eliminationKey(label)
  return [4, 0, '', 0, label]
}

const collate = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true })
const byGroup = (a: string, b: string): number => {
  const x = groupKey(a), y = groupKey(b)
  return x[0] - y[0] || x[1] - y[1] || collate(x[2], y[2]) || x[3] - y[3] || collate(x[4], y[4])
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
  const all = list.map(c => ({ c, l: levelsOf(c) }))
  const ambitos = unique(all.map(x => x.l.ambito)).sort(byAmbito)
  const ambito = resolve(ambitos, wanted.ambito)
  const inAmbito = all.filter(x => x.l.ambito === ambito)
  const categories = unique(inAmbito.map(x => x.l.category)).sort((a, b) => CATEGORIES.indexOf(a) - CATEGORIES.indexOf(b))
  const category = resolve(categories, wanted.category)
  const inCategory = inAmbito.filter(x => x.l.category === category)
  const seasons = unique(inCategory.map(x => x.l.season)).sort((a, b) => b.localeCompare(a))
  const season = resolve(seasons, wanted.season)
  const inSeason = inCategory.filter(x => x.l.season === season)
  const competitions = unique(inSeason.map(x => x.l.competition)).sort((a, b) => a.localeCompare(b))
  const competition = resolve(competitions, wanted.competition)
  const inCompetition = inSeason.filter(x => x.l.competition === competition)
  const groups = unique(inCompetition.map(x => x.l.group)).sort(byGroup)
  const group = resolve(groups, wanted.group)
  const collection = inCompetition.find(x => x.l.group === group)?.c ?? null
  return { ambitos, categories, seasons, competitions, groups, selection: { ambito, category, season, competition, group }, collection }
}

/** The levels of a collection (the header starts on the current one). */
export const selectionOf = levelsOf

/** «SEGUNDA FEB 2026/2027 Liga Regular B»: what a collection is called on the home page. */
export function collectionLabel(c: CollectionInfo): string {
  const { competition, season, group } = levelsOf(c)
  return [competition, season, group].filter(Boolean).join(' ')
}
