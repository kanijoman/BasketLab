import { existsSync, readFileSync } from 'node:fs'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Page } from '@playwright/test'

// What the Talent e2e shares: the publication of the exporter served in place of `raw.githubusercontent.com` (the base of `market/data.ts`), and the pages and sizes the specs go through.
const DATA = join(fileURLToPath(new URL('.', import.meta.url)), '../../tests/local_vectors/talent_data')
export const BASE = 'https://raw.githubusercontent.com/kanijoman/BasketLab/talent-data/'

export interface Serve {
  /** Files answered with 404 (path relative to the publication), as if they were missing. */
  missing?: (path: string) => boolean
  /** Files answered with 500. */
  broken?: (path: string) => boolean
}

/** Serve the real publication from the vectors: every request to the base of `talent-data` is answered from disk, so the browser opens the real sealed files with the real open key. */
export async function serveTalent(page: Page, options: Serve = {}): Promise<void> {
  await page.route(`${BASE}**`, route => {
    const path = decodeURIComponent(route.request().url().slice(BASE.length).split('?')[0])
    const file = join(DATA, path)
    if (options.broken?.(path)) return route.fulfill({ status: 500, body: '' })
    if (options.missing?.(path) || !existsSync(file)) return route.fulfill({ status: 404, body: '' })
    return route.fulfill({ body: readFileSync(file), contentType: extname(file) === '.json' ? 'application/json' : 'text/plain' })
  })
}

export const ANA = 'feb:10100'                  // LF2 2025 and, linked to her, a FBCYL season (2026)
export const WITH_SHOTS = 'feb:10101'
export const NO_SHOTS = 'feb:10200'
export const FBCYL_LINKED = 'fbcyl:34004-08'    // linked to Ana
export const FBCYL_ALONE = 'fbcyl:34001-00'     // nobody's link
export const enc = encodeURIComponent

export const WIDTHS = [320, 412, 1280] as const

/** The pages of Talent with data, by name: what the layout and accessibility specs go through. */
export const PAGES: [string, string][] = [
  ['buscador', '/?s=2026'],
  ['buscador-feb', '/?s=2025'],
  ['ficha', `/jugador/${enc(WITH_SHOTS)}`],
  ['ficha-fbcyl', `/jugador/${enc(FBCYL_ALONE)}`],
  ['ficha-unificada', `/jugador/${enc(ANA)}`],
  ['comparador', `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)},${enc(FBCYL_ALONE)}`],
  ['comparador-vacio', '/comparar'],
]

/** Open a page and wait until it has stopped loading: the spinner is gone and the network is quiet. */
export async function open(page: Page, path: string): Promise<void> {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
  await page.getByRole('status', { name: /Cargando/ }).waitFor({ state: 'detached' }).catch(() => undefined)
}
