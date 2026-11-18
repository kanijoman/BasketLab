// The static host of `web-data` for tests (issues #328, #639, #845): serves the files of the REAL publication of the exporter (`tests/local_vectors/web_data`, made by
// `generate_web_data.py`) as `fetch` answers. `override` swaps or removes some (a manifest without the open key, a file that has gone: `null` is a 404).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { vi } from 'vitest'

export const WEB_DATA_DIR = join(__dirname, '../../../tests/local_vectors/web_data')
export const WEB_BASE = 'https://data.test/'
export const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
export const FBCYL = 'FBCYL_1ª_FASE-GRUPO_A-1_2026_'

export const readPublished = (file: string) => readFileSync(join(WEB_DATA_DIR, file), 'utf-8')

export interface WebDataHost {
  /** The files asked of the host, in order. */
  requested: string[]
  override: Record<string, string | null>
}

/** Installs a static host over `dir` as `fetch` (the files of a REAL publication of an exporter) and returns what it was asked and the overrides. */
export function serveDirectory(dir: string, hostBase: string): WebDataHost {
  const host: WebDataHost = { requested: [], override: {} }
  globalThis.fetch = vi.fn(async (input: string | URL | Request) => {
    const file = String(input).replace(hostBase, '')
    host.requested.push(file)
    const body = file in host.override ? host.override[file] : readFileSync(join(dir, file), 'utf-8')
    return body === null
      ? { ok: false, status: 404, text: async () => '', json: async () => ({}) }
      : { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  }) as unknown as typeof fetch
  return host
}

/** The host of `web-data` for tests (empty overrides: the publication as the exporter wrote it). */
export const serveWebData = (): WebDataHost => serveDirectory(WEB_DATA_DIR, WEB_BASE)

export const WEB_EXT_DIR = join(__dirname, '../../../tests/local_vectors/web_data_ext')
export const EXT_BASE = 'https://ext.test/'
export const FIBA = 'FIBA_U18_EuroBasket_2026_'
export const NCAA = 'NCAA_D1_2026_SEC'

export interface TwoHosts { web: WebDataHost; ext: WebDataHost }

/** The two publications at once (#884): web-data at WEB_BASE and web-data-ext at EXT_BASE, each with what it was asked and its own overrides (a `null` override of `index.json` is a host that is down). */
export function serveBoth(): TwoHosts {
  const web: WebDataHost = { requested: [], override: {} }
  const ext: WebDataHost = { requested: [], override: {} }
  const answer = (host: WebDataHost, dir: string, file: string) => {
    host.requested.push(file)
    const body = file in host.override ? host.override[file] : readFileSync(join(dir, file), 'utf-8')
    return body === null ? { ok: false, status: 404, text: async () => '', json: async () => ({}) } : { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  }
  globalThis.fetch = vi.fn(async (input: string | URL | Request) => {
    const url = String(input)
    if (url.startsWith(EXT_BASE)) return answer(ext, WEB_EXT_DIR, url.slice(EXT_BASE.length))
    return answer(web, WEB_DATA_DIR, url.slice(WEB_BASE.length))
  }) as unknown as typeof fetch
  return { web, ext }
}
