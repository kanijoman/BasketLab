// The local data source (issue #327, step 2): the tables of the web computed from the files `run_local_export.py` writes, instead of the API.
// Off by default; `?data=local` turns it on (and remembers it), `?data=api` off. Every function answers `null` when it cannot (switch off,
// competition not exported, no player rows, file missing or of another format) so that the caller falls back to the API.
import type { PlayerStat } from '@/api/client'
import { aggregatePlayers, type PlayerGameRow, type PlayerTableFilter } from './aggregatePlayers'
import { aggregateTeams, type GameRow, type TeamTableFilter, type TeamTables } from './aggregateTeams'

export const DATA_FLAG_KEY = 'basketlab.data'
const FORMAT = 1

interface IndexEntry { name: string; file: string; league: 'feb' | 'fbcyl'; games: number; bytes: number }
interface Competition { format: number; collection: string; league: 'feb' | 'fbcyl'; games: number; team_rows: GameRow[]; player_rows: PlayerGameRow[] | null }

let indexLoad: Promise<IndexEntry[] | null> | null = null
const competitions = new Map<string, Promise<Competition | null>>()

/** Forget what was loaded (tests, or after a new export). */
export function resetLocalData(): void {
  indexLoad = null
  competitions.clear()
}

/** Whether the tables come from the local files. `?data=local` / `?data=api` in the address set it; the choice survives in `localStorage`. */
export function localDataEnabled(): boolean {
  try {
    const asked = new URLSearchParams(window.location.search).get('data')
    if (asked === 'local') localStorage.setItem(DATA_FLAG_KEY, 'local')
    else if (asked === 'api') localStorage.removeItem(DATA_FLAG_KEY)
    return localStorage.getItem(DATA_FLAG_KEY) === 'local'
  } catch {
    return false                                                  // private window or blocked storage: the API
  }
}

const url = (file: string) => `${import.meta.env.BASE_URL}local-data/${encodeURI(file)}`

async function fetchJson<T>(file: string): Promise<T | null> {
  try {
    const res = await fetch(url(file))
    return res.ok ? ((await res.json()) as T) : null
  } catch {
    return null
  }
}

function loadIndex(): Promise<IndexEntry[] | null> {
  if (!indexLoad) {
    indexLoad = fetchJson<{ format: number; collections: IndexEntry[] }>('index.json').then(index => (index?.format === FORMAT ? index.collections : null))
    indexLoad.then(list => { if (!list) indexLoad = null })       // a failed load is not remembered
  }
  return indexLoad
}

function loadCompetition(name: string): Promise<Competition | null> {
  let load = competitions.get(name)
  if (!load) {
    load = loadIndex().then(async list => {
      const entry = list?.find(c => c.name === name)
      const data = entry ? await fetchJson<Competition>(entry.file) : null
      return data?.format === FORMAT ? data : null
    })
    competitions.set(name, load)
    load.then(data => { if (!data) competitions.delete(name) })
  }
  return load
}

/** `{team_stats, opponent_stats}` of the competition with the filters, or `null` to use the API. */
export async function localTeamStats(collection: string, filters: TeamTableFilter): Promise<TeamTables | null> {
  if (!localDataEnabled()) return null
  const data = await loadCompetition(collection)
  return data ? aggregateTeams(data.team_rows, filters) : null
}

/** The player table of the competition with the filters, or `null` to use the API (FBCYL has no player rows yet, #644). */
export async function localPlayerStats(collection: string, filters: PlayerTableFilter): Promise<PlayerStat[] | null> {
  if (!localDataEnabled()) return null
  const data = await loadCompetition(collection)
  return data?.player_rows ? aggregatePlayers(data.player_rows, data.team_rows, filters) : null
}
