// What the refresh publishes for the web (issues #328, #640, #639): the `web-data` branch, read through a static host with no server. The manifest
// `index.json` is the only file that keeps its name; everything else carries the hash of its content, so a file is never read in a version that is not
// the manifest's. Reports are sealed by scope: this opens them with the open key the manifest publishes while the beta lasts and with the invitations
// (rights) of the reader. Unlocking is the live app's (`@live-package`): one implementation until the shared interface (#330).
// Everything here answers `WebDataUnavailable` when the data cannot be had (host down, schema unknown, not published) so that the caller falls back
// to the API, and lets `ScopedAccessError` through: «you have no key for this» is not «try the API».
import { decryptScoped, PackageDecryptError, ScopedAccessError } from '@live-package/crypto'
import { loadRights, scopeKeys } from '@live-package/rights'
import type { ReportMode, TeamReport } from '@/api/teamReport'
import type { ScoutingReport, ScoutingScope } from '@/api/scoutingRival'
import { WEB_DATA_SCHEMA, type ReportEntry, type ReportIndex, type ReportIndexEntry, type Wrap, type WebDataManifest } from './contract.generated'
import { DataUnavailable } from '@/datasource/resolve'
import type { Competition } from '@/localdata/competition'
import type { Lineups } from '@/localdata/lineups'
import type { Derived } from '@/localdata/pbp'
import type { Shots } from '@/localdata/shots'
import type { MatchAnalysis, MatchSummary, PossessionStat, RotationResult, TeamConsistencyResponse } from '@/api/client'

export const SCHEMA = WEB_DATA_SCHEMA
const DEFAULT_BASE = 'https://raw.githubusercontent.com/kanijoman/BasketLab/web-data/'

/** The data cannot be had from `web-data`: the caller falls back to the API. */
export class WebDataUnavailable extends DataUnavailable {}

// The shape of the manifest and of the report indexes is generated from the Python contract (`src/local_data/contract.py`, issue #328)
export type { FileEntry, ReportEntry, ReportIndex, ReportIndexEntry, RowsEntry, Wrap, WebDataManifest } from './contract.generated'

let base: string = (import.meta.env.VITE_DATA_BASE as string | undefined) || DEFAULT_BASE
let manifestLoad: Promise<WebDataManifest> | null = null
const indexes = new Map<string, Promise<ReportIndex>>()

/** Where the publication is (tests, or a host other than the default). */
export function setDataBase(url: string): void {
  base = url.endsWith('/') ? url : `${url}/`
  resetWebData()
}

/** Forget what was loaded (tests, or a manifest that was replaced). */
export function resetWebData(): void {
  manifestLoad = null
  indexes.clear()
}

class Gone extends Error {}                                      // 404: the file of a publication that has been replaced

async function fetchText(file: string): Promise<string> {
  let res: Response
  try {
    res = await fetch(base + file)
  } catch {
    throw new WebDataUnavailable('No se pudo conectar con los datos publicados.')
  }
  if (res.status === 404) throw new Gone(file)
  if (!res.ok) throw new WebDataUnavailable(`Los datos publicados no responden (HTTP ${res.status}).`)
  return res.text()
}

async function fetchJson<T>(file: string): Promise<T> {
  try {
    return JSON.parse(await fetchText(file)) as T
  } catch (error) {
    if (error instanceof Gone) throw new WebDataUnavailable('Los datos publicados no están disponibles.')
    if (error instanceof WebDataUnavailable) throw error
    throw new WebDataUnavailable('Los datos publicados están dañados.')
  }
}

function loadManifest(): Promise<WebDataManifest> {
  if (!manifestLoad) {
    manifestLoad = fetchJson<WebDataManifest>('index.json').then(manifest => {
      if (manifest?.schema !== SCHEMA) throw new WebDataUnavailable(`Versión de los datos publicados no soportada (${manifest?.schema}). Actualiza la página.`)
      return manifest
    })
    manifestLoad.catch(() => { manifestLoad = null })           // a failed load is not remembered
  }
  return manifestLoad
}

function loadIndex(entry: ReportIndexEntry): Promise<ReportIndex> {
  let load = indexes.get(entry.file)
  if (!load) {
    load = fetchJson<ReportIndex>(entry.file)                   // the name carries the hash of the content: it can be kept for as long as the page lives
    indexes.set(entry.file, load)
    load.catch(() => indexes.delete(entry.file))
  }
  return load
}

async function reportIndexOf(collection: string): Promise<{ manifest: WebDataManifest; index: ReportIndex }> {
  const manifest = await loadManifest()
  const entry = manifest.reports.find(r => r.collection === collection)
  if (!entry) throw new WebDataUnavailable('Esta competición no tiene informes publicados.')
  return { manifest, index: await loadIndex(entry) }
}

/** The teams that have reports in the competition, by name. */
export async function loadReportTeams(collection: string): Promise<Array<{ id: string; name: string }>> {
  const { index } = await reportIndexOf(collection)
  const teams = new Map(index.reports.map(r => [r.team_id, r.team]))
  return [...teams].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name))
}

/** A sealed file of the publication with the manifest it came from, the wraps of its key and its text. */
interface Sealed { manifest: WebDataManifest; wraps: Wrap[]; text: string }

/** The sealed file of the first report of the competition that `find` accepts, with the manifest it came from. */
async function sealedFile(collection: string, find: (entry: ReportEntry) => boolean): Promise<Sealed> {
  const { manifest, index } = await reportIndexOf(collection)
  const entry = index.reports.find(find)
  if (!entry) throw new WebDataUnavailable('Este informe no está publicado.')
  return { manifest, wraps: entry.wraps, text: await fetchText(entry.file) }
}

/** The sealed rows of a competition (`rows/`), with the manifest they came from. */
async function sealedRows(collection: string): Promise<Sealed> {
  const manifest = await loadManifest()
  const entry = manifest.rows.find(r => r.collection === collection)
  if (!entry) throw new WebDataUnavailable('Esta competición no tiene datos publicados.')
  return { manifest, wraps: entry.wraps, text: await fetchText(entry.file) }
}

/** A sealed file a competition has besides its rows (`derived/`, `shots/`, `rotations/`), with the manifest it came from. */
async function sealedSection(section: 'derived' | 'shots' | 'rotations' | 'matches' | 'possessions' | 'possession_csv' | 'lineups', collection: string, missing: string): Promise<Sealed> {
  const manifest = await loadManifest()
  const entry = (manifest[section] ?? []).find(r => r.collection === collection)
  if (!entry) throw new WebDataUnavailable(missing)
  return { manifest, wraps: entry.wraps, text: await fetchText(entry.file) }
}

const sealedDerived = (collection: string) => sealedSection('derived', collection, 'Esta competición no tiene el análisis pbp publicado.')

/**
 * Opens a sealed file of the publication with the open key and the rights of the reader. A file that is gone (the publication moved on while the
 * page was open) makes it read the manifest again, once.
 * @throws ScopedAccessError the reader has no key that opens it (ask for an invitation)
 * @throws WebDataUnavailable it cannot be had from the publication (use the API)
 */
async function openSealed<T>(locate: () => Promise<Sealed>, what: string): Promise<T> {
  let sealed
  try {
    sealed = await locate()
  } catch (error) {
    if (!(error instanceof Gone)) throw error
    resetWebData()
    try {
      sealed = await locate()
    } catch (again) {
      throw again instanceof Gone ? new WebDataUnavailable('Los datos publicados han cambiado: recarga la página.') : again
    }
  }
  try {
    return JSON.parse(await decryptScoped(sealed.text, sealed.wraps, scopeKeys(sealed.manifest, loadRights()))) as T
  } catch (error) {
    if (error instanceof ScopedAccessError) throw error
    if (error instanceof PackageDecryptError || error instanceof SyntaxError) throw new WebDataUnavailable(`${what} publicado está dañado.`)
    throw error
  }
}

/** The report of a team (its own analysis or the rule-based report of a rival). */
export const loadWebReport = (collection: string, teamId: string, mode: ReportMode): Promise<TeamReport> =>
  openSealed<TeamReport>(() => sealedFile(collection, r => r.team_id === teamId && r.mode === mode), 'El informe')

/** The full scouting of a rival for a scope: `liga`, `copa` (the cups of the season) or `todo` (both), issue #638. */
export const loadWebScouting = (collection: string, teamId: string, scope: ScoutingScope): Promise<ScoutingReport> =>
  openSealed<ScoutingReport>(() => sealedFile(collection, r => r.team_id === teamId && r.mode === 'scouting' && r.scope === scope), 'El informe')

/** The names of the competitions the publication has rows for (the phases of a competition are found among them), issue #671. */
export async function loadWebCollections(): Promise<string[]> {
  return (await loadManifest()).rows.map(r => r.collection)
}

/** The rows of the contract of a competition (what its season tables are computed from on the device), issue #673. */
export const loadWebRows = (collection: string): Promise<Competition> => openSealed<Competition>(() => sealedRows(collection), 'El fichero')

const SCOPE_ORDER: ScoutingScope[] = ['liga', 'copa', 'todo']

/** The scopes the scouting of a team is published for, the league first; none if the team has no scouting (FBCYL, or no play-by-play). */
export async function loadScoutingScopes(collection: string, teamId: string): Promise<ScoutingScope[]> {
  const { index } = await reportIndexOf(collection)
  const have = new Set(index.reports.filter(r => r.team_id === teamId && r.mode === 'scouting' && r.scope).map(r => r.scope as ScoutingScope))
  return SCOPE_ORDER.filter(scope => have.has(scope))
}

/** The `DERIVED` of each game of a competition (what the pbp tables are summed from on the device), issue #676. */
export const loadWebDerived = (collection: string): Promise<Derived> => openSealed<Derived>(() => sealedDerived(collection), 'El fichero')

/** The shots of a competition (the zones, their rating and the scatter are counted from them on the device), issue #685. */
export const loadWebShots = (collection: string): Promise<Shots> =>
  openSealed<Shots>(() => sealedSection('shots', collection, 'Esta competición no tiene los tiros publicados.'), 'El fichero')

/** What `GET /rotaciones/{collection}/{team_id}` answers for each team of a competition (computed when it was published), issue #684. */
export interface Rotations {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  teams: { team_id: string; team_name: string; analysis: RotationResult }[]
}
export const loadWebRotations = (collection: string): Promise<Rotations> =>
  openSealed<Rotations>(() => sealedSection('rotations', collection, 'Esta competición no tiene las rotaciones publicadas.'), 'El fichero')

/** The per-game counters of the lineups of every team of a competition (`lineups/`), issue #686: the browser merges them into the tables of Combinaciones. */
export const loadWebLineups = (collection: string): Promise<Lineups> =>
  openSealed<Lineups>(() => sealedSection('lineups', collection, 'Esta competición no tiene las combinaciones publicadas.'), 'El fichero')

/** The list of the matches of a competition, each with its analysis (computed when it was published), issue #677. */
export interface PublishedMatches {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  games: number
  matches: (MatchSummary & { analysis: MatchAnalysis | null })[]
}
export const loadWebMatches = (collection: string): Promise<PublishedMatches> =>
  openSealed<PublishedMatches>(() => sealedSection('matches', collection, 'Esta competición no tiene los partidos publicados.'), 'El fichero')

/** The possessions page of a competition as the endpoints answer it (computed when it was published), issue #679. */
export interface PublishedPossessions {
  format: number
  collection: string
  league: 'feb' | 'fbcyl'
  table: PossessionStat[]
  consistency: TeamConsistencyResponse
  /** The quality CSV, without the BOM (the download adds it once, at its start). */
  quality_csv: string
}
export const loadWebPossessions = (collection: string): Promise<PublishedPossessions> =>
  openSealed<PublishedPossessions>(() => sealedSection('possessions', collection, 'Esta competición no tiene las posesiones publicadas.'), 'El fichero')

/** The per-possession CSV of a competition (the heavy file: it is read only when its button is pressed). */
export interface PublishedPossessionCsv { format: number; collection: string; league: 'feb' | 'fbcyl'; games: number; csv: string }
export const loadWebPossessionCsv = (collection: string): Promise<PublishedPossessionCsv> =>
  openSealed<PublishedPossessionCsv>(() => sealedSection('possession_csv', collection, 'Esta competición no tiene el CSV de posesiones publicado.'), 'El fichero')
