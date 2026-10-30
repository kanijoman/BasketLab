// The local data source (issue #327, step 2): the tables of the web computed from the files `run_local_export.py` writes, instead of the API.
// Which datasets read it is the switch of `datasource/switch` (`?data=local`, `?data=local:team-stats,…`, `?data=api`). Every function answers `null` when it cannot (switch off,
// competition not exported, no player rows, file missing or of another format) so that the caller falls back to the API.
import type { LineupRow, PlayerStat } from '@/api/client'
import { aggregatePlayers, type PlayerGameRow, type PlayerTableFilter } from './aggregatePlayers'
import { aggregatePlayersFbcyl, type FbcylPlayerGameRow } from './aggregatePlayersFbcyl'
import { aggregateTeams, type TeamTableFilter, type TeamTables } from './aggregateTeams'
import { compareTeams } from './comparison'
import type { Competition } from './competition'
import { competitionEvolution, EVOLUTION_STATS } from './evolution'
import type { ComparisonKind, CompetitionEvolutionPoint, TeamComparison, TeamStat } from '@/api/client'
import { dataSourceOf } from '@/datasource/switch'
import { lineupAnalysis, type LineupQuery, type Lineups } from './lineups'
import { mergeByKey, siblingCollections } from './multiPhase'
import { byPeriod, derivedCoverage, pointsByOrigin, situations, timeoutEffects, type Derived } from './pbp'
import type { DerivedCoverage, OriginRow, PeriodRow, SituationRow, TimeoutRow } from '@/api/pbpExtended'
import { shotRaw, shotZones, type ShotFilter, type Shots } from './shots'
import type { MatchAnalysis, MatchSummary, PossessionStat, RotationResult, TeamConsistencyResponse, ShotRawData, ShotZoneData } from '@/api/client'
import { loadWebCollections, loadWebDerived, loadWebLineups, loadWebMatches, loadWebPossessionCsv, loadWebPossessions, loadWebRotations, loadWebRows, loadWebShots, WebDataUnavailable, type PublishedMatches, type PublishedPossessionCsv, type PublishedPossessions, type Rotations } from '@/webdata/client'

// the switch lives in `datasource/switch` (issue #329); these two are what this module's callers and tests have always imported from here
export { DATA_FLAG_KEY, localDataEnabled } from '@/datasource/switch'
const FORMAT = 1

interface IndexEntry { name: string; file: string; league: 'feb' | 'fbcyl'; games: number; bytes: number }

let indexLoad: Promise<IndexEntry[] | null> | null = null
const competitions = new Map<string, Promise<Competition | null>>()
const derivedLoads = new Map<string, Promise<Derived | null>>()
const shotLoads = new Map<string, Promise<Shots | null>>()
const rotationLoads = new Map<string, Promise<Rotations | null>>()
const lineupLoads = new Map<string, Promise<Lineups | null>>()
const matchLoads = new Map<string, Promise<PublishedMatches | null>>()
const possessionLoads = new Map<string, Promise<PublishedPossessions | null>>()
const possessionCsvLoads = new Map<string, Promise<PublishedPossessionCsv | null>>()

/** Forget what was loaded (tests, or after a new export). */
export function resetLocalData(): void {
  indexLoad = null
  competitions.clear()
  derivedLoads.clear()
  shotLoads.clear()
  rotationLoads.clear()
  lineupLoads.clear()
  matchLoads.clear()
  possessionLoads.clear()
  possessionCsvLoads.clear()
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

/** The rows of the publication (`rows/` of web-data, sealed by competition: the open key of the beta or the invitations of the reader), issue #673. `null` if it is not
 *  published; a reader without the key gets the access error (it is not «try elsewhere»). */
async function publishedRows(name: string): Promise<Competition | null> {
  try {
    const data = await loadWebRows(name)
    return data.format === FORMAT ? data : null
  } catch (error) {
    if (error instanceof WebDataUnavailable) return null
    throw error
  }
}

/** The manual export of development (`local-data/`, `run_local_export.py`). */
async function exportedRows(name: string): Promise<Competition | null> {
  const list = await loadIndex()
  const entry = list?.find(c => c.name === name)
  const data = entry ? await fetchJson<Competition>(entry.file) : null
  return data?.format === FORMAT ? data : null
}

function loadCompetition(name: string): Promise<Competition | null> {
  let load = competitions.get(name)
  if (!load) {
    load = publishedRows(name).then(published => published ?? exportedRows(name))
    competitions.set(name, load)
    load.then(data => { if (!data) competitions.delete(name) }, () => competitions.delete(name))
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
  return data ? playerTable(data, filters) : null
}

/** The player table of a competition's rows (each league has its own), or `null` if it was exported without player rows. */
function playerTable(data: Competition, filters: PlayerTableFilter): PlayerStat[] | null {
  if (!data.player_rows) return null
  return data.league === 'fbcyl'
    ? aggregatePlayersFbcyl(data.player_rows as FbcylPlayerGameRow[], data.team_rows, filters)
    : aggregatePlayers(data.player_rows as PlayerGameRow[], data.team_rows, filters)
}

/** The comparison of the teams (home vs away, won vs lost, a stretch vs the rest, issue #670), or `null` to use the API (the dataset is off, the competition is not
 *  published, or the comparison cannot be answered here: a stretch with no date). */
export async function localTeamComparison(collection: string, by: ComparisonKind, range?: { from?: string; to?: string }): Promise<TeamComparison | null> {
  if (dataSourceOf('team-comparison') !== 'local') return null
  const data = await loadCompetition(collection)
  return data ? compareTeams(data.team_rows, by, range) : null
}

/** The rows of every collection, or `null` if one of them is not published (merging only some of the phases would be a wrong answer). */
async function allCompetitions(collections: string[]): Promise<Competition[] | null> {
  const loaded = await Promise.all(collections.map(loadCompetition))
  return loaded.every(data => data !== null) ? (loaded as Competition[]) : null
}

/** Multifase (issue #671): one merged row per team over the phases, as `GET /multi/team-stats`, or `null` to use the API. */
export async function localMultiTeamStats(collections: string[]): Promise<TeamStat[] | null> {
  if (dataSourceOf('multi-phase') !== 'local') return null
  const all = await allCompetitions(collections)
  if (!all) return null
  const tables = Object.fromEntries(all.map((data, i) => [collections[i], aggregateTeams(data.team_rows, {}).team_stats as unknown as Array<Record<string, unknown>>]))
  return mergeByKey(tables, 'team_name') as unknown as TeamStat[]
}

/** One merged row per player over the phases, as `GET /multi/player-stats`, or `null` to use the API. */
export async function localMultiPlayerStats(collections: string[]): Promise<PlayerStat[] | null> {
  if (dataSourceOf('multi-phase') !== 'local') return null
  const all = await allCompetitions(collections)
  const tables = all?.map(data => playerTable(data, {}))
  if (!all || !tables || tables.some(t => t === null)) return null
  return mergeByKey(Object.fromEntries(tables.map((t, i) => [collections[i], t as unknown as Array<Record<string, unknown>>])), 'player_name') as unknown as PlayerStat[]
}

/** The phases of a competition among the published ones (the names of the manifest; the manual export in development), or `null` to use the API. */
export async function localSiblingCollections(collection: string): Promise<string[] | null> {
  if (dataSourceOf('multi-phase') !== 'local') return null
  let names: string[] | null = null
  try {
    names = await loadWebCollections()
  } catch (error) {
    if (!(error instanceof WebDataUnavailable)) throw error
    names = (await loadIndex())?.map(c => c.name) ?? null
  }
  return names ? siblingCollections(collection, names) : null
}

/** Evolución (issue #672): the competition-wide rolling and cumulative averages by game number, as `GET /teams/{collection}/competition-evolution`, or `null` to use the
 *  API (the dataset is off, the competition is not published, or the window is one the API refuses: 2 to 15 games). */
export async function localCompetitionEvolution(collection: string, stat: string, window: number): Promise<CompetitionEvolutionPoint[] | null> {
  if (dataSourceOf('evolution') !== 'local') return null
  if (!Number.isInteger(window) || window < 2 || window > 15) return null
  const data = await loadCompetition(collection)
  const known = (EVOLUTION_STATS as readonly string[]).includes(stat)
  return data ? competitionEvolution(data.team_rows, known ? stat : 'points', window) : null           // the router reads an unknown stat as points
}

/** The `DERIVED` of each game of a competition (the published `derived/`; there is no manual export of it), or `null` if it is not published. A reader without the key gets the access error. */
function loadDerived(name: string): Promise<Derived | null> {
  let load = derivedLoads.get(name)
  if (!load) {
    load = loadWebDerived(name).then(data => (data.format === FORMAT ? data : null), error => {
      if (error instanceof WebDataUnavailable) return null
      throw error
    })
    derivedLoads.set(name, load)
    load.then(data => { if (!data) derivedLoads.delete(name) }, () => derivedLoads.delete(name))
  }
  return load
}

/** One of the pbp tables of the competition (issue #676), or `null` to use the API (the dataset is off or the competition has no published `DERIVED`). */
async function pbpTable<T>(collection: string, table: (derived: Derived) => T): Promise<T | null> {
  if (dataSourceOf('pbp') !== 'local') return null
  const derived = await loadDerived(collection)
  return derived ? table(derived) : null
}

export const localPointsByOrigin = (collection: string): Promise<OriginRow[] | null> => pbpTable(collection, pointsByOrigin)
export const localByPeriod = (collection: string): Promise<PeriodRow[] | null> => pbpTable(collection, byPeriod)
export const localSituations = (collection: string): Promise<SituationRow[] | null> => pbpTable(collection, situations)
export const localTimeoutEffects = (collection: string): Promise<TimeoutRow[] | null> => pbpTable(collection, timeoutEffects)
export const localDerivedCoverage = (collection: string): Promise<DerivedCoverage | null> => pbpTable(collection, derivedCoverage)

/** A file of the publication that is read once per competition and kept; `null` if it is not published, the access error for a reader without the key (#684, #685). */
function loadOnce<T extends { format: number }>(cache: Map<string, Promise<T | null>>, name: string, load: (name: string) => Promise<T>): Promise<T | null> {
  let pending = cache.get(name)
  if (!pending) {
    pending = load(name).then(data => (data.format === FORMAT ? data : null), error => {
      if (error instanceof WebDataUnavailable) return null
      throw error
    })
    cache.set(name, pending)
    pending.then(data => { if (!data) cache.delete(name) }, () => cache.delete(name))
  }
  return pending
}

/** Tiros (issue #685): the zones of a team, a player or the league, with their rating against the league, as `GET /shots/{collection}`; `null` to use the API. */
export async function localShotZones(collection: string, params: ShotFilter & { compare?: 'league' }): Promise<ShotZoneData[] | null> {
  if (dataSourceOf('shots') !== 'local') return null
  const shots = await loadOnce(shotLoads, collection, loadWebShots)
  return shots ? shotZones(shots, params) : null
}

/** The raw shots, as `GET /shots/{collection}/raw`; `null` to use the API. */
export async function localShotRaw(collection: string, params: ShotFilter & { limit?: number }): Promise<ShotRawData[] | null> {
  if (dataSourceOf('shots') !== 'local') return null
  const shots = await loadOnce(shotLoads, collection, loadWebShots)
  return shots ? shotRaw(shots, params) : null
}

/** Rotaciones (issue #684): the analysis of a team as the endpoint answers it, computed when the competition was published; `null` to use the API (it is not published, or the
 *  team is not in it). */
export async function localRotation(collection: string, teamId: string): Promise<RotationResult | null> {
  if (dataSourceOf('rotations') !== 'local') return null
  const rotations = await loadOnce(rotationLoads, collection, loadWebRotations)
  return rotations?.teams.find(team => team.team_id === String(teamId))?.analysis ?? null
}

/** Combinaciones (issue #686): the table of a team as `GET /lineups/{collection}/{team_id}` answers it, merged on the device from the per-game counters of the publication; `null`
 *  to use the API (it is not published, or the team is not in it). */
export async function localLineups(collection: string, teamId: string, query: LineupQuery): Promise<LineupRow[] | null> {
  if (dataSourceOf('lineups') !== 'local') return null
  const published = await loadOnce(lineupLoads, collection, loadWebLineups)
  return published ? lineupAnalysis(published, teamId, query) : null
}

/** Partidos (issue #677): the list of the matches of a competition, as `GET /matches/{collection}`; `null` to use the API. */
export async function localMatchList(collection: string): Promise<MatchSummary[] | null> {
  if (dataSourceOf('matches') !== 'local') return null
  const published = await loadOnce(matchLoads, collection, loadWebMatches)
  return published ? published.matches.map(({ analysis: _analysis, ...summary }) => summary) : null
}

/** The analysis of a match, as `GET /matches/{collection}/{id}`; `null` to use the API (it is not published, or the match is not in the publication). */
export async function localMatchAnalysis(collection: string, matchId: string | number): Promise<MatchAnalysis | null> {
  if (dataSourceOf('matches') !== 'local') return null
  const published = await loadOnce(matchLoads, collection, loadWebMatches)
  return published?.matches.find(match => String(match.match_id) === String(matchId))?.analysis ?? null
}

/** Posesiones (issue #679): the table of the page, as `GET /possessions/{collection}`; `null` to use the API. */
export async function localPossessionStats(collection: string): Promise<PossessionStat[] | null> {
  if (dataSourceOf('possessions') !== 'local') return null
  return (await loadOnce(possessionLoads, collection, loadWebPossessions))?.table ?? null
}

/** The consistency of the teams, as `GET /teams/{collection}/consistency`, from the same published file as the table; `null` to use the API. */
export async function localTeamConsistency(collection: string): Promise<TeamConsistencyResponse | null> {
  if (dataSourceOf('possessions') !== 'local') return null
  return (await loadOnce(possessionLoads, collection, loadWebPossessions))?.consistency ?? null
}

/** The text of the CSV the page offers (`possessions`: one row per possession; `quality`: PBP against the box score), or `null` to use the API. The per-possession file is the
 *  heavy one and is read only here, when its button is pressed. */
export async function localPossessionCsv(collection: string, kind: 'possessions' | 'quality'): Promise<string | null> {
  if (dataSourceOf('possessions') !== 'local') return null
  if (kind === 'quality') return (await loadOnce(possessionLoads, collection, loadWebPossessions))?.quality_csv ?? null
  return (await loadOnce(possessionCsvLoads, collection, loadWebPossessionCsv))?.csv ?? null
}
