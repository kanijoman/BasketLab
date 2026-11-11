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

/** Installs the host as `fetch` and returns what it was asked and the overrides (empty: the publication as the exporter wrote it). */
export function serveWebData(): WebDataHost {
  const host: WebDataHost = { requested: [], override: {} }
  globalThis.fetch = vi.fn(async (input: string | URL | Request) => {
    const file = String(input).replace(WEB_BASE, '')
    host.requested.push(file)
    const body = file in host.override ? host.override[file] : readPublished(file)
    return body === null
      ? { ok: false, status: 404, text: async () => '', json: async () => ({}) }
      : { ok: true, status: 200, text: async () => body, json: async () => JSON.parse(body) }
  }) as unknown as typeof fetch
  return host
}
