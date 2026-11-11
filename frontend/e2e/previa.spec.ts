import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// The preview of the match (issue #849) in a real browser against the REAL publication of the exporter (tests/local_vectors/web_data), served in place of the `web-data` branch: choose a team, see its
// calendar of matches to play, choose one, and read the forecast. The publication is the small league of the fixtures (12 games): enough for the forecast, too few scenarios to describe the game
// (the page says so), so what is drawn in full is covered by the unit tests; this one checks that the page works and fits a phone.
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

test('choose a team, see its calendar, choose the match and read the forecast, on a phone', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.setViewportSize({ width: 390, height: 800 })
  await page.goto(`/${C}/previa?data=local`)
  await expect(page.getByText('Elige tu equipo para ver sus próximos partidos.')).toBeVisible()

  await page.getByRole('combobox', { name: 'Equipo' }).selectOption({ label: 'ALPHA' })
  const fixtures = page.getByTestId('fixture')
  await expect(fixtures).toHaveCount(3)                                             // the three matches of the third leg of the fixture league
  await expect(fixtures.first()).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('heading', { name: 'Pronóstico' })).toBeVisible()
  await expect(page.getByText('Probabilidad de victoria', { exact: true })).toBeVisible()
  const first = await page.getByTestId('preview-title').textContent()

  await fixtures.nth(1).click()
  await expect(page).toHaveURL(/partido=/)
  await expect(fixtures.nth(1)).toHaveAttribute('aria-pressed', 'true')
  expect(await page.getByTestId('preview-title').textContent()).not.toBe(first)

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)                                           // nothing scrolls sideways at 390 px
  expect(errors).toEqual([])
})

test('the page is reloaded on the same match from its address', async ({ page }) => {
  await page.goto(`/${C}/previa?data=local`)
  await page.getByRole('combobox', { name: 'Equipo' }).selectOption({ label: 'ALPHA' })
  await page.getByTestId('fixture').nth(2).click()
  await expect(page.getByTestId('fixture').nth(2)).toHaveAttribute('aria-pressed', 'true')
  const title = await page.getByTestId('preview-title').textContent()
  await page.reload()
  await expect(page.getByTestId('preview-title')).toHaveText(title!)
})

for (const theme of ['light', 'dark'] as const) {
  test(`no accessibility violations: ${theme}, 390 px`, async ({ page }) => {
    await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
    await page.setViewportSize({ width: 390, height: 800 })
    await page.goto(`/${C}/previa?data=local`)
    await page.getByRole('combobox', { name: 'Equipo' }).selectOption({ label: 'ALPHA' })
    await expect(page.getByRole('heading', { name: 'Pronóstico' })).toBeVisible()
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    expect(result.violations.map(v => `${v.id}: ${v.nodes[0]?.target.join(' ')}`)).toEqual([])
  })
}
