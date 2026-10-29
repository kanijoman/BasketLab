// The local data source (issue #327, step 2): the tables of the web computed from the files `run_local_export.py` writes, instead of the API.
// Which datasets read it is the switch of `datasource/switch` (`?data=local`, `?data=local:team-stats,…`, `?data=api`). Every function answers `null` when it cannot (switch off,
// competition not exported, no player rows, file missing or of another format) so that the caller falls back to the API.
import type { PlayerStat } from '@/api/client'
import { aggregatePlayers, type PlayerGameRow, type PlayerTableFilter } from './aggregatePlayers'
import { aggregatePlayersFbcyl, type FbcylPlayerGameRow } from './aggregatePlayersFbcyl'
import { aggregateTeams, type GameRow, type TeamTableFilter, type TeamTables } from './aggregateTeams'
import { dataSourceOf } from '@/datasource/switch'

// the switch lives in `datasource/switch` (issue #329); these two are what this module's callers and tests have always imported from here
export { DATA_FLAG_KEY, localDataEnabled } from '@/datasource/switch'
const FORMAT = 1

interface IndexEntry { name: string; file: string; league: 'feb' | 'fbcyl'; games: number; bytes: number }
interface Competition { format: number; collection: string; league: 'feb' | 'fbcyl'; games: number; team_rows: GameRow[]; player_rows: PlayerGameRow[] | FbcylPlayerGameRow[] | null }

let indexLoad: Promise<IndexEntry[] | null> | null = null
const competitions = new Map<string, Promise<Competition | null>>()

/** Forget what was loaded (tests, or after a new export). */
export function resetLocalData(): void {
  indexLoad = null
  competitions.clear()
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
  if (dataSourceOf('team-stats') !== 'local') return null
  const data = await loadCompetition(collection)
  return data ? aggregateTeams(data.team_rows, filters) : null
}

/** The player table of the competition with the filters (each league has its own table), or `null` to use the API (a competition exported without player rows). */
export async function localPlayerStats(collection: string, filters: PlayerTableFilter): Promise<PlayerStat[] | null> {
  if (dataSourceOf('player-stats') !== 'local') return null
  const data = await loadCompetition(collection)
  if (!data?.player_rows) return null
  return data.league === 'fbcyl'
    ? aggregatePlayersFbcyl(data.player_rows as FbcylPlayerGameRow[], data.team_rows, filters)
    : aggregatePlayers(data.player_rows as PlayerGameRow[], data.team_rows, filters)
}
