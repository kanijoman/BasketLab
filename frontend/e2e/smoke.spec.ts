import { expect, test, type Page } from '@playwright/test'

const COLLECTION = 'L_F_-2_2025_2026_Liga_Regular_B'
const TEAM = 'ACEITES ABRIL ADBA SANFER'

/** Fail the test on any uncaught error of the page. */
function collectErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  return errors
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
})

test('home lists the competition, hides the internal collection and opens it', async ({ page }) => {
  const errors = collectErrors(page)
  await page.goto('/')
  await expect(page.getByText('BasketLab').first()).toBeVisible()
  await expect(page.getByText(/Liga_Regular/).first()).toBeVisible()
  await expect(page.getByText('COLLECTION_META')).toHaveCount(0)
  await page.getByText(/Liga_Regular/).first().click()
  await expect(page).toHaveURL(new RegExp(`/${COLLECTION}$`))
  expect(errors).toEqual([])
})

test('team statistics table shows the teams of the collection', async ({ page }) => {
  const errors = collectErrors(page)
  await page.goto(`/${COLLECTION}/teams`)
  await expect(page.getByRole('table')).toBeVisible()
  await expect(page.getByText(TEAM).first()).toBeVisible()
  expect(errors).toEqual([])
})

test('possessions: summary by default, grouped fast/medium/slow in the own-style view, full team name', async ({ page }) => {
  const errors = collectErrors(page)
  await page.goto(`/${COLLECTION}/possessions`)
  const team = page.getByTitle(TEAM).first()
  await expect(team).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'DER' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Rápidas' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Estilo propio' }).click()
  await expect(page.getByRole('columnheader', { name: 'Rápidas' })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'DER' })).toHaveCount(0)

  // every view fits the viewport: the table does not need horizontal scrolling
  const scrolls = await page.locator('div.overflow-x-auto').first().evaluate(el => el.scrollWidth > el.clientWidth)
  expect(scrolls).toBe(false)
  expect(errors).toEqual([])
})

test('the API behind the page is healthy', async ({ request }) => {
  const live = await request.get('/api/v1/health')
  expect(await live.json()).toMatchObject({ status: 'ok' })
  const db = await request.get('/api/v1/health/db')
  expect(await db.json()).toMatchObject({ connected: true })
})
