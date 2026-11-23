import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

// The WHOLE analysis of the preview (issue #949) in a real browser: the publication of `previa.spec.ts` is a league of 12 games, too few scenarios (`MIN_POOL` = 30) to describe the match, so this
// one serves a real competition big enough, the LF Challenge 2026-27 of `tests/fixtures/forecast` (39 games, 240 matches in the calendar), sealed by the exporter's own code
// (`tests/e2e_web/forecast_publication.py`) in place of the `web-data` branch: the scenarios, the goals and the card «¿Y si…?» at 390 px, its three conditions, the address and axe.
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '../..')
const C = 'LF_CHALLENGE_2026_2027_Liga_Regular_Único'
const RAW = /^https:\/\/raw\.githubusercontent\.com\/kanijoman\/BasketLab\/web-data\/(.*)$/
const CARD = '¿Y si…? Probabilidad con condiciones'
let dir = ''

test.beforeAll(() => {
  dir = mkdtempSync(join(tmpdir(), 'basketlab-previa-'))
  execFileSync(process.env.E2E_PYTHON ?? 'python', [join(ROOT, 'tests/e2e_web/forecast_publication.py'), dir], { stdio: 'inherit' })
})

async function servePublication(page: Page) {
  await page.route(RAW, route => {
    const file = decodeURIComponent(RAW.exec(route.request().url())![1])
    try {
      return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: readFileSync(join(dir, file)) })
    } catch {
      return route.fulfill({ status: 404, headers: { 'access-control-allow-origin': '*' }, body: '' })
    }
  })
}

/** Opens the preview of the first match to play of the first team that has one. */
async function openPreview(page: Page, query = '') {
  await page.goto(`/${encodeURIComponent(C)}/previa?data=local${query}`)
  const team = page.getByRole('combobox', { name: 'Equipo' })
  await expect(team).toBeVisible()
  await team.selectOption({ index: 1 })
  await expect(page.getByTestId('fixture').first()).toHaveAttribute('aria-pressed', 'true')
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('e2e-started')) { localStorage.clear(); sessionStorage.setItem('e2e-started', '1') }
  })
  await page.clock.setFixedTime(new Date('2026-11-09T12:00:00Z'))           // the publication is a capture of that day: «next match» reads the clock
  await servePublication(page)
})

test('with enough games the page draws the whole analysis, and the card takes up to three conditions without scrolling sideways, on a phone', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.setViewportSize({ width: 390, height: 800 })
  await openPreview(page)
  for (const name of ['Pronóstico', 'Escenarios', 'Objetivos del partido', CARD, 'Emparejamiento']) await expect(page.getByRole('heading', { name })).toBeVisible()
  await expect(page.getByText(/pocos datos|pocos escenarios/i)).toHaveCount(0)             // the small-pool notice is gone: the analysis is complete

  const card = page.getByLabel(CARD)
  await expect(card.getByRole('heading', { name: /^Nuestros puntos: más de \d+$/ })).toBeVisible()
  await expect(card.getByText(/^Pasa en \d+ de cada 100 partidos como este\./)).toBeVisible()
  await card.getByRole('button', { name: 'Añadir condición' }).click()
  await card.getByRole('button', { name: 'Añadir condición' }).click()
  await expect(card.getByTestId('condition')).toHaveCount(3)
  await expect(card.getByRole('button', { name: 'Añadir condición' })).toHaveCount(0)      // three is the most a question has
  await expect(card.getByRole('heading', { name: /^Nuestros puntos: más de \d+, Sus puntos: más de \d+ y Nuestro acierto de tiro \(eFG\): más del [\d,]+ %$/ })).toBeVisible()

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)                                                   // nothing scrolls sideways at 390 px, with the three conditions and their table
  expect(errors).toEqual([])
})

test('the conditions go to the address and come back from it on a reload', async ({ page }) => {
  await openPreview(page)
  const card = page.getByLabel(CARD)
  await card.getByRole('button', { name: 'Añadir condición' }).click()
  await expect(page).toHaveURL(/si=[^&]*own\.points\.gt\.\d+[^&]*_/)                       // two conditions joined by «_»
  const title = /^Nuestros puntos: más de \d+ y /
  const heading = await card.getByRole('heading', { name: title }).textContent()
  await page.reload()
  await expect(page.getByLabel(CARD).getByTestId('condition')).toHaveCount(2)
  await expect(page.getByLabel(CARD).getByRole('heading', { name: title })).toHaveText(heading!)
})

test('a shared address with a question opens on it', async ({ page }) => {
  await openPreview(page)
  const where = new URL(page.url())
  where.searchParams.set('si', 'own.points.gt.70_rival.efg.lt.40')
  await page.goto(where.toString())
  const card = page.getByLabel(CARD)
  await expect(card.getByTestId('condition')).toHaveCount(2)
  await expect(card.getByRole('heading', { name: /^Nuestros puntos: más de 70 y Su acierto de tiro \(eFG\): menos del 40 %$/ })).toBeVisible()
})

for (const theme of ['light', 'dark'] as const) {
  test(`no accessibility violations with the whole analysis and three conditions: ${theme}, 390 px`, async ({ page }) => {
    await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
    await page.setViewportSize({ width: 390, height: 800 })
    await openPreview(page, '')
    const card = page.getByLabel(CARD)
    await card.getByRole('button', { name: 'Añadir condición' }).click()
    await card.getByRole('button', { name: 'Añadir condición' }).click()
    await expect(card.getByTestId('condition')).toHaveCount(3)
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    expect(result.violations.map(v => `${v.id}: ${v.nodes[0]?.target.join(' ')}`)).toEqual([])
  })
}
