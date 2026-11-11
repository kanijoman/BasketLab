// What the page remembers in the browser of whoever reads it, per competition (#849, #850): the own team and the cut lines. A per-viewer convenience: storage can be blocked, empty or damaged
// (a private window, cleared site data) and the page must work without it, so every access is guarded and anything that is not what was written is the default.
import type { Cut } from './decisive'

export type { Cut } from './decisive'

export interface ForecastPrefs {
  /** The own team of the preview. */
  team?: string
  /** The lines the reader drew in the table of the league: the first n or the last n. */
  cuts: Cut[]
}

const key = (collection: string): string => `basketlab.forecast.${collection}`

const isCut = (value: unknown): value is Cut => {
  const c = value as Cut | null
  return typeof c === 'object' && c !== null && (c.kind === 'top' || c.kind === 'bottom') && Number.isInteger(c.n) && c.n >= 1
}

export function loadPrefs(collection: string): ForecastPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(key(collection)) ?? 'null') as { team?: unknown; cuts?: unknown } | null
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return { cuts: [] }
    return { ...(typeof raw.team === 'string' && raw.team ? { team: raw.team } : {}), cuts: Array.isArray(raw.cuts) ? raw.cuts.filter(isCut) : [] }
  } catch {
    return { cuts: [] }
  }
}

/** Saves what changes (`team: undefined` forgets the team); the rest stays as it was. */
export function savePrefs(collection: string, change: Partial<ForecastPrefs>): void {
  try {
    const next = { ...loadPrefs(collection), ...change }
    localStorage.setItem(key(collection), JSON.stringify({ ...(next.team ? { team: next.team } : {}), cuts: next.cuts }))
  } catch {
    /* blocked: it is only a convenience */
  }
}
