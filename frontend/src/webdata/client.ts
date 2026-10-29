// What the refresh publishes for the web (issues #328, #640, #639): the `web-data` branch, read through a static host with no server. The manifest
// `index.json` is the only file that keeps its name; everything else carries the hash of its content, so a file is never read in a version that is not
// the manifest's. Reports are sealed by scope: this opens them with the open key the manifest publishes while the beta lasts and with the invitations
// (rights) of the reader. Unlocking is the live app's (`@live-package`): one implementation until the shared interface (#330).
// Everything here answers `WebDataUnavailable` when the data cannot be had (host down, schema unknown, not published) so that the caller falls back
// to the API, and lets `ScopedAccessError` through: «you have no key for this» is not «try the API».
import { decryptScoped, PackageDecryptError, ScopedAccessError } from '@live-package/crypto'
import { loadRights, scopeKeys } from '@live-package/rights'
import type { ReportMode, TeamReport } from '@/api/teamReport'
import { WEB_DATA_SCHEMA, type ReportEntry, type ReportIndex, type ReportIndexEntry, type WebDataManifest } from './contract.generated'
import { DataUnavailable } from '@/datasource/resolve'

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

async function sealedReport(collection: string, teamId: string, mode: ReportMode): Promise<{ manifest: WebDataManifest; entry: ReportEntry; text: string }> {
  const { manifest, index } = await reportIndexOf(collection)
  const entry = index.reports.find(r => r.team_id === teamId && r.mode === mode)
  if (!entry) throw new WebDataUnavailable('Este informe no está publicado.')
  return { manifest, entry, text: await fetchText(entry.file) }
}

/**
 * The report of a team, opened with the open key and the rights of the reader. A file that is gone (the publication moved on while the page was
 * open) makes it read the manifest again, once.
 * @throws ScopedAccessError the reader has no key that opens it (ask for an invitation)
 * @throws WebDataUnavailable it cannot be had from the publication (use the API)
 */
export async function loadWebReport(collection: string, teamId: string, mode: ReportMode): Promise<TeamReport> {
  let sealed
  try {
    sealed = await sealedReport(collection, teamId, mode)
  } catch (error) {
    if (!(error instanceof Gone)) throw error
    resetWebData()
    try {
      sealed = await sealedReport(collection, teamId, mode)
    } catch (again) {
      throw again instanceof Gone ? new WebDataUnavailable('Los datos publicados han cambiado: recarga la página.') : again
    }
  }
  try {
    return JSON.parse(await decryptScoped(sealed.text, sealed.entry.wraps, scopeKeys(sealed.manifest, loadRights()))) as TeamReport
  } catch (error) {
    if (error instanceof ScopedAccessError) throw error
    if (error instanceof PackageDecryptError || error instanceof SyntaxError) throw new WebDataUnavailable('El informe publicado está dañado.')
    throw error
  }
}
