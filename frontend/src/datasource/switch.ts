// The switch of the local-first migration (issue #329): which datasets the web reads from the published files (`localdata`, `webdata`) and which from the
// API, so that the pages move one at a time instead of all at once. `?data=local` turns every dataset on, `?data=local:team-report,team-stats` only those,
// `?data=api` none; the choice is remembered in the browser (`localStorage`). Anything else in `?data=` is ignored. Without storage (private window,
// blocked) everything reads the API.

/** What a page reads, by the answer it needs (the pages that share an answer share its switch). Which pages read what: docs/ARCHITECTURE.md. */
export const DATASETS = ['team-stats', 'player-stats', 'team-report', 'report-teams'] as const
export type Dataset = (typeof DATASETS)[number]

export const DATA_FLAG_KEY = 'basketlab.data'

const FORM = /^local(?::(.*))?$/

/** Applies `?data=` (and remembers it) and returns what is on: the remembered choice, `local` (all) or the list after `local:`. */
function state(): string | null {
  try {
    const asked = new URLSearchParams(window.location.search).get('data')
    if (asked === 'api') localStorage.removeItem(DATA_FLAG_KEY)
    else if (asked !== null && FORM.test(asked)) localStorage.setItem(DATA_FLAG_KEY, asked)
    return localStorage.getItem(DATA_FLAG_KEY)
  } catch {
    return null                                                  // private window or blocked storage: the API
  }
}

/** The datasets that read the local files now. */
export function localDatasets(): Dataset[] {
  const match = state()?.match(FORM)
  if (!match) return []
  if (match[1] === undefined) return [...DATASETS]
  const listed = new Set(match[1].split(',').map(name => name.trim()))
  return DATASETS.filter(dataset => listed.has(dataset))
}

export const dataSourceOf = (dataset: Dataset): 'local' | 'api' => (localDatasets().includes(dataset) ? 'local' : 'api')

/** Whether any dataset reads the local files (what the header says). */
export const localDataEnabled = (): boolean => localDatasets().length > 0
