/**
 * Packages published by the `live-packages.yml` workflow (issue #175) on the `live-packages` branch:
 * `index.json` lists them, each one is `<team_id>/<rival_id>.bpkg` (encrypted, see crypto.ts). raw.githubusercontent.com
 * sends `access-control-allow-origin: *`, so a plain fetch works from the WebView.
 */
export const PACKAGES_BASE_URL = 'https://raw.githubusercontent.com/kanijoman/BasketLab/live-packages'
const INDEX_VERSION = 1

export interface PackageIndexEntry {
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

export interface PackageIndex {
  v: number
  generated_at?: string
  packages: PackageIndexEntry[]
}

/** The part of ``fetch`` that is used (so tests can pass a light fake). */
export type Fetcher = (url: string, init?: RequestInit) => Promise<Pick<Response, 'ok' | 'status' | 'text' | 'json'>>

const OFFLINE = 'Sin conexión con GitHub: se sigue usando el paquete guardado en el dispositivo.'

async function get(url: string, fetcher: Fetcher): Promise<Awaited<ReturnType<Fetcher>>> {
  let res: Awaited<ReturnType<Fetcher>>
  try {
    // the CDN caches for ~5 minutes; the checksum in the index guards against a stale file
    res = await fetcher(url, { cache: 'no-cache' })
  } catch {
    throw new Error(OFFLINE)
  }
  if (!res.ok) throw new Error(`No se pudo descargar (HTTP ${res.status}). ¿Se ha publicado ya el paquete?`)
  return res
}

export async function fetchIndex(fetcher: Fetcher = (u, i) => fetch(u, i)): Promise<PackageIndex> {
  const index = (await (await get(`${PACKAGES_BASE_URL}/index.json`, fetcher)).json()) as PackageIndex
  if (index.v !== INDEX_VERSION) throw new Error(`Versión del índice de paquetes no soportada (${index.v}). Actualiza la app.`)
  return { ...index, packages: index.packages ?? [] }
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
