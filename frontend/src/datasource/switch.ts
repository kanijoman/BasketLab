// The switch of the local-first migration (issues #329, #334): which datasets the web reads from the published files (`localdata`, `webdata`) and which from the
// API. Since #334 the DEFAULT is the published files for every dataset (the API is only the fallback when they cannot answer, and goes away with Render): `?data=api`
// forces the API for everything, `?data=local` goes back to the default and `?data=local:team-report,team-stats` turns on only those; the choice is remembered in the
// browser (`localStorage`). Anything else in `?data=` is ignored. Without storage (private window, blocked) the default applies, and `?data=api` still works for the page.

/** What a page reads, by the answer it needs (the pages that share an answer share its switch). Which pages read what: docs/ARCHITECTURE.md. */
export const DATASETS = ['collections', 'team-stats', 'player-stats', 'team-comparison', 'multi-phase', 'evolution', 'pbp', 'shots', 'rotations', 'lineups', 'inout', 'player-consistency', 'rival-adjusted', 'matches', 'possessions', 'team-report', 'report-teams', 'scouting', 'weekly-report'] as const
export type Dataset = (typeof DATASETS)[number]

export const DATA_FLAG_KEY = 'basketlab.data'

const FORM = /^local(?::(.*))?$/
const DEFAULT = 'local'

/** Whether `value` is a choice the switch understands: `api` or `local` with an optional list. */
const isChoice = (value: string | null): value is string => value !== null && (value === 'api' || FORM.test(value))

/** Applies `?data=` (and remembers it when it can) and returns what is on: the asked choice, the remembered one or the default. */
function state(): string {
  let asked: string | null = null
  try { asked = new URLSearchParams(window.location.search).get('data') } catch { /* no window */ }
  try {
    if (isChoice(asked)) localStorage.setItem(DATA_FLAG_KEY, asked)
    else {
      const stored = localStorage.getItem(DATA_FLAG_KEY)
      return isChoice(stored) ? stored : DEFAULT              // nothing remembered, or a damaged value: the default
    }
  } catch {
    return isChoice(asked) ? asked : DEFAULT                  // private window or blocked storage: what the URL asks for, else the default
  }
  return asked
}

/** The datasets that read the local files now. */
export function localDatasets(): Dataset[] {
  const match = state().match(FORM)
  if (!match) return []                                       // `api`
  if (match[1] === undefined) return [...DATASETS]
  const listed = new Set(match[1].split(',').map(name => name.trim()))
  return DATASETS.filter(dataset => listed.has(dataset))
}

export const dataSourceOf = (dataset: Dataset): 'local' | 'api' => (localDatasets().includes(dataset) ? 'local' : 'api')

/** The datasets that read the API now (what the header warns about). */
export const apiDatasets = (): Dataset[] => {
  const local = new Set(localDatasets())
  return DATASETS.filter(dataset => !local.has(dataset))
}

/** Whether any dataset reads the local files. */
export const localDataEnabled = (): boolean => localDatasets().length > 0
