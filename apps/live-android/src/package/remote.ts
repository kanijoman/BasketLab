/**
 * Packages published by the `live-packages.yml` workflow (issue #175) on the `live-packages` branch:
 * `index.json` lists them, each one is `<team_id>/<rival_id>.bpkg` (encrypted, see crypto.ts). raw.githubusercontent.com
 * sends `access-control-allow-origin: *`, so a plain fetch works from the WebView.
 */
export const PACKAGES_BASE_URL = 'https://raw.githubusercontent.com/kanijoman/BasketLab/live-packages'
import type { Wrap } from './crypto'
import { isFavorite, type Favorite } from './favorites'

/** Version 1: encrypted with a password. Version 2 (issue #410): sealed by scope, the keys wrapped per scope are in `wraps` and the index publishes
 *  `open_key` while the beta is open. */
const INDEX_VERSIONS = [1, 2]

/** Structured data of the competition of an entry (publisher, issue #438); absent in an index from before it existed. */
export interface CompetitionInfo {
  key: string
  label: string
  competition: string
  group: string
  season: string
  level: number | null
  gender: 'M' | 'F' | null
}

export interface PackageIndexEntry {
  competition?: CompetitionInfo
  /** Present when sealed by scope (index v2); without it the file is opened with the password. */
  wraps?: Wrap[]
  team_id: string
  rival_id: string
  rival: string
  file: string
  sha256: string
  bytes: number
  match: {
    code: string
    start?: string | null
    round?: number | null
    home?: { id: string; name: string } | null
    away?: { id: string; name: string } | null
  }
}

/** One match of a published round (issues #286, #172): enough to list it without downloading the bundle. */
export interface RoundMatch {
  code: string
  start?: string | null
  home: { id: string; name: string }
  away: { id: string; name: string }
  /** The team whose point of view the DEFAULT package has (the club's when it plays the match, else the home team). */
  own_id: string
  /** Every team the match can be followed as (both teams, the default one first); absent in an index from before it existed. */
  own_ids?: string[]
  is_club: boolean
}

/** The bundle of the next round of a competition: ONE encrypted, compressed file with the package of every match. */
export interface RoundIndexEntry {
  wraps?: Wrap[]
  competition?: CompetitionInfo
  collection: string
  round: number | null
  file: string
  sha256: string
  bytes: number
  /** The club plays in this round. */
  club: boolean
  matches: RoundMatch[]
}

export interface PackageIndex {
  v: number
  generated_at?: string
  /** The key (base64) of the open scope, while the beta is open: the app opens the packages with it, no password. */
  open_key?: string | null
  packages: PackageIndexEntry[]
  /** Rounds of every competition; absent in an index that predates them. */
  rounds: RoundIndexEntry[]
  club_team_id?: string | null
}

/** The part of ``fetch`` that is used (so tests can pass a light fake). */
export type Fetcher = (url: string, init?: RequestInit) => Promise<Pick<Response, 'ok' | 'status' | 'text' | 'json'>>

const OFFLINE = 'Sin conexión con GitHub: se sigue usando el paquete guardado en el dispositivo. Revisa la conexión y vuelve a intentarlo.'

async function get(url: string, fetcher: Fetcher): Promise<Awaited<ReturnType<Fetcher>>> {
  let res: Awaited<ReturnType<Fetcher>>
  try {
    // the CDN caches for ~5 minutes; the checksum in the index guards against a stale file
    res = await fetcher(url, { cache: 'no-cache' })
  } catch {
    throw new Error(OFFLINE)
  }
  if (!res.ok) throw new Error(`No se pudo descargar (HTTP ${res.status}). ¿Se ha publicado ya el paquete? Prueba a actualizar la lista en unos minutos.`)
  return res
}

export async function fetchIndex(fetcher: Fetcher = (u, i) => fetch(u, i)): Promise<PackageIndex> {
  const index = (await (await get(`${PACKAGES_BASE_URL}/index.json`, fetcher)).json()) as PackageIndex
  if (!INDEX_VERSIONS.includes(index.v)) throw new Error(`Versión del índice de paquetes no soportada (${index.v}). Actualiza la app.`)
  return { ...index, packages: index.packages ?? [], rounds: index.rounds ?? [] }
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('')
}

/** The encrypted envelope text, verified against the checksum of the index. */
export async function fetchPackageText(entry: PackageIndexEntry, fetcher: Fetcher = (u, i) => fetch(u, i)): Promise<string> {
  const text = await (await get(`${PACKAGES_BASE_URL}/${entry.file}`, fetcher)).text()
  if ((await sha256Hex(text)) !== entry.sha256) {
    throw new Error('El paquete descargado no coincide con el índice (caché o fichero dañado). Reintenta en unos minutos.')
  }
  return text
}

/** The encrypted bundle text of a round, verified against the checksum of the index. */
export async function fetchRoundText(entry: RoundIndexEntry, fetcher: Fetcher = (u, i) => fetch(u, i)): Promise<string> {
  const text = await (await get(`${PACKAGES_BASE_URL}/${entry.file}`, fetcher)).text()
  if ((await sha256Hex(text)) !== entry.sha256) {
    throw new Error('La jornada descargada no coincide con el índice (caché o fichero dañado). Reintenta en unos minutos.')
  }
  return text
}

/** `LF_CHALLENGE_2026_2027_Liga_Regular_Único` -> `LF CHALLENGE 2026 2027 Liga Regular Único` (what an index without competition data shows). */
export function competitionLabel(collection: string): string {
  return collection.replace(/_+/g, ' ').trim()
}

/** The rounds with a team of interest first, then the competition of the club; in each round the matches of the teams of interest first, then
 *  those of the club, then by kick-off. Without favourites it is the order it always was. */
export function orderRounds(rounds: RoundIndexEntry[], favorites: Favorite[] = []): RoundIndexEntry[] {
  const interesting = (m: RoundMatch) => Number(isFavorite(favorites, m.home.id, m.home.name) || isFavorite(favorites, m.away.id, m.away.name))
  const byTime = (a: RoundMatch, b: RoundMatch) => interesting(b) - interesting(a) || Number(b.is_club) - Number(a.is_club) || (a.start ?? '').localeCompare(b.start ?? '')
  const rank = (r: RoundIndexEntry) => (r.matches.some(m => interesting(m)) ? 1 : 0)
  return [...rounds]
    .sort((a, b) => rank(b) - rank(a) || Number(b.club) - Number(a.club) || a.collection.localeCompare(b.collection))
    .map(round => ({ ...round, matches: [...round.matches].sort(byTime) }))
}

export interface RoundBundle {
  v: number
  collection: string
  round: number | null
  matches: { match: RoundMatch & { round?: number | null }; own_id: string; rival_id: string; is_club: boolean; /** the package envelope text */ package: string }[]
}

const BUNDLE_VERSION = 1

/** The plaintext of a decrypted bundle; refuses another version or something that is not a round. */
export function parseRoundBundle(text: string): RoundBundle {
  let bundle: Partial<RoundBundle>
  try {
    bundle = JSON.parse(text)
  } catch {
    throw new Error('El fichero descargado no es una jornada de BasketLab.')
  }
  if (!bundle || typeof bundle !== 'object' || !Array.isArray(bundle.matches)) throw new Error('El fichero descargado no es una jornada de BasketLab.')
  if (bundle.v !== BUNDLE_VERSION) throw new Error(`Versión de jornada no soportada (${bundle.v}). Actualiza la app.`)
  return bundle as RoundBundle
}

/** The sides of a match that can be followed: both teams, or just the default one in an older index. */
export function sidesOf(match: RoundMatch): string[] {
  return match.own_ids && match.own_ids.length ? match.own_ids : [match.own_id]
}

/** The package text of a match as seen from ``ownId``; a bundle published before both sides existed has only the first one of the match.
 *  Null when the match is not in the bundle. */
export function pickPackage(bundle: RoundBundle, code: string, ownId: string): string | null {
  const ofMatch = bundle.matches.filter(m => m.match.code === code)
  return (ofMatch.find(m => m.own_id === ownId) ?? ofMatch[0])?.package ?? null
}
