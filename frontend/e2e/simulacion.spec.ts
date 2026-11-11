import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// The simulation of the league (issue #850) in a real browser against the REAL publication of the exporter (tests/local_vectors/web_data), served in place of the `web-data` branch: the fixture
// league has four teams, twelve games played and six to play. It checks the flow (a cut line is drawn, remembered across a reload and removed), that nothing scrolls sideways on a phone and the
// accessibility of the page in both themes.
const DIR = join(dirname(fileURLToPath(import.meta.url)), '../../tests/local_vectors/web_data')
const C = 'L_F_-2_2025_2026_Liga_Regular_B'
const RAW = /^https:\/\/raw\.githubusercontent\.com\/kanijoman\/BasketLab\/web-data\/(.*)$/

async function servePublication(page: Page) {
  await page.route(RAW, route => {
    const file = RAW.exec(route.request().url())![1]
    try {
      return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: readFileSync(join(DIR, file)) })
    } catch {
      return route.fulfill({ status: 404, headers: { 'access-control-allow-origin': '*' }, body: '' })
    }
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('e2e-started')) { localStorage.clear(); sessionStorage.setItem('e2e-started', '1') }
  })
  await servePublication(page)
})

test('the table, the heat map and a cut line that survives a reload, on a phone', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto(`/${C}/simulacion?data=local`)
  await expect(page.getByRole('heading', { name: 'Clasificación proyectada' })).toBeVisible()
  await expect(page.getByRole('table', { name: 'Probabilidad de cada puesto final' })).toBeVisible()
  await expect(page.getByText(/No se modelan ascensos, descensos ni playoffs/)).toBeVisible()

  await page.getByLabel('Tipo de línea').selectOption('top')
  await page.getByLabel('Número de equipos').fill('2')
  await page.getByRole('button', { name: 'Añadir línea' }).click()
  await expect(page.getByText('Entre los 2 primeros').first()).toBeVisible()          // on a phone the table is cards: the label is repeated in each

  await page.reload()
  await expect(page.getByText('Entre los 2 primeros').first()).toBeVisible()
  await page.getByRole('button', { name: 'Quitar la línea Primeros 2' }).click()
  await expect(page.getByText('Entre los 2 primeros')).toHaveCount(0)

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)                                           // the heat map scrolls inside its box, never the page
  expect(errors).toEqual([])
})

test('the team of the reader brings its decisive games', async ({ page }) => {
  await page.goto(`/${C}/simulacion?data=local`)
  await page.getByLabel('Tu equipo').selectOption({ label: 'ALPHA' })
  await expect(page.getByRole('region', { name: 'Partidos decisivos' })).toBeVisible()
  expect(await page.getByTestId('decisive').count()).toBeGreaterThan(0)
})

for (const theme of ['light', 'dark'] as const) {
  test(`no accessibility violations: ${theme}, 390 px`, async ({ page }) => {
    await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
    await page.setViewportSize({ width: 390, height: 800 })
    await page.goto(`/${C}/simulacion?data=local`)
    await page.getByLabel('Tu equipo').selectOption({ label: 'ALPHA' })
    await expect(page.getByRole('region', { name: 'Partidos decisivos' })).toBeVisible()
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    expect(result.violations.map(v => `${v.id}: ${v.nodes[0]?.target.join(' ')}`)).toEqual([])
  })
}
