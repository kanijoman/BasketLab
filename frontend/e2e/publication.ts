import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Page } from '@playwright/test'

// The REAL publication of the exporter (tests/local_vectors/web_data: the small league of the fixtures, FEB and FBCYL), served in place of the `web-data` branch: the web reads the published
// files and nothing else (the API was retired, epic #1199), so every e2e that needs data takes it from here. No credentials, no network.
const DIR = join(dirname(fileURLToPath(import.meta.url)), '../../tests/local_vectors/web_data')
const RAW = /^https:\/\/raw\.githubusercontent\.com\/kanijoman\/BasketLab\/web-data\/(.*)$/

export const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
export const TEAM = 'ALPHA'

export async function servePublication(page: Page): Promise<void> {
  await page.route(RAW, route => {
    const file = RAW.exec(route.request().url())![1]
    try {
      return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: readFileSync(join(DIR, file)) })
    } catch {
      return route.fulfill({ status: 404, headers: { 'access-control-allow-origin': '*' }, body: '' })
    }
  })
}
