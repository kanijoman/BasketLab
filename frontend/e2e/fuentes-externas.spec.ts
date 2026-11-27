import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// The external sources (ACB, FIBA, NCAA; #884, PR C) in a real browser against the TWO REAL publications of the exporter (`tests/local_vectors/web_data` and `web_data_ext`), served in place of the `web-data` and
// `web-data-ext` branches. In the second one FIBA is fresh and NCAA failed on its last run (its last good data is from 17/11): the discreet notice must say so, fit a phone, and the selector must offer the sources.
const VECTORS = join(dirname(fileURLToPath(import.meta.url)), '../../tests/local_vectors')
const NCAA = 'NCAA_D1_2026_SEC'
const FIBA = 'FIBA_U18_EuroBasket_2026_'
const RAW = /^https:\/\/raw\.githubusercontent\.com\/kanijoman\/BasketLab\/(web-data|web-data-ext)\/(.*)$/

async function servePublications(page: Page) {
  await page.route(RAW, route => {
    const [, branch, file] = RAW.exec(route.request().url())!
    try {
      return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: readFileSync(join(VECTORS, branch === 'web-data' ? 'web_data' : 'web_data_ext', decodeURIComponent(file))) })
    } catch {
      return route.fulfill({ status: 404, headers: { 'access-control-allow-origin': '*' }, body: '' })
    }
  })
}

// The publication is a fixture frozen on 18/11/2026: the notice of freshness compares it with the clock, so the browser's clock is frozen the day after (#1023); with the real one the fine source went stale.
const TODAY = new Date('2026-11-19T07:00:00Z')

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(TODAY)
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('e2e-started')) { localStorage.clear(); sessionStorage.setItem('e2e-started', '1') }
  })
  await servePublications(page)
})

test('an external competition says its data is from the day it last worked, and fits a phone', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto(`/${NCAA}/teams`)
  const notice = page.getByRole('status').filter({ hasText: 'Datos de NCAA del 17/11' })
  await expect(notice).toBeVisible()
  await expect(notice).toContainText('la última actualización falló')
  expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0)      // nothing scrolls sideways at 390 px
  expect(errors).toEqual([])
})

test('a competition of a source that is fine shows no notice', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto(`/${FIBA}/teams`)
  await expect(page.getByRole('combobox', { name: 'Ámbito' })).toHaveValue('FIBA')            // the page and its selectors are there
  await expect(page.getByRole('status').filter({ hasText: 'Datos de' })).toHaveCount(0)
})

test('the selector of the header offers the sources next to FEB and FBCYL and goes to the competition of the one chosen', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto(`/${NCAA}/teams`)
  const ambito = page.getByRole('combobox', { name: 'Ámbito' })
  await expect(ambito).toBeVisible()
  expect(await ambito.locator('option').allTextContents()).toEqual(['FEB', 'FBCYL', 'FIBA', 'NCAA'])
  await expect(ambito).toHaveValue('NCAA')
  await expect(page.getByRole('combobox', { name: 'Competición' })).toHaveValue('NCAA D1')
  await ambito.selectOption('FIBA')
  await expect(page).toHaveURL(new RegExp(`/${FIBA}/teams`))
})

for (const theme of ['light', 'dark'] as const) {
  test(`no accessibility violations with the notice of a stale source: ${theme}, 390 px`, async ({ page }) => {
    await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
    await page.setViewportSize({ width: 390, height: 800 })
    await page.goto(`/${NCAA}/teams`)
    await expect(page.getByRole('status').filter({ hasText: 'Datos de NCAA' })).toBeVisible()
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    expect(result.violations.map(v => `${v.id}: ${v.nodes[0]?.target.join(' ')}`)).toEqual([])
  })
}
