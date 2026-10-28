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
  // a clean start once per test: a reload keeps what the test stored (the theme chosen)
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('e2e-started')) { localStorage.clear(); sessionStorage.setItem('e2e-started', '1') }
  })
})

test('opens in the light theme even on a dark device, keeps the one chosen and paints it before the app runs (#188)', async ({ page }) => {
  const errors = collectErrors(page)
  const background = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  expect(await background()).toBe('rgb(246, 248, 250)')

  await page.getByRole('radiogroup', { name: 'Tema' }).getByRole('radio', { name: 'Oscuro' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await background()).toBe('rgb(13, 17, 23)')

  // without the scripts of the app the page is still dark: the first script of index.html chose it before anything painted
  await page.route('**/*.{js,tsx,ts}', route => route.abort())
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await background()).toBe('rgb(13, 17, 23)')
  expect(errors).toEqual([])
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

test('on a phone a table is a list of cards and no value leaves its card (#184)', async ({ page }) => {
  const errors = collectErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/${COLLECTION}/possessions`)
  const card = page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: TEAM }) })
  await expect(card).toBeVisible()
  await expect(page.locator('table')).toHaveCount(0)
  const right = await card.evaluate(el => el.getBoundingClientRect().right)
  const values = await card.locator('dd').evaluateAll(els => els.map(e => e.getBoundingClientRect().right))
  expect(values.length).toBeGreaterThan(3)
  for (const v of values) expect(v).toBeLessThanOrEqual(right)
  expect(errors).toEqual([])
})

test('on a phone the navigation is a menu, it reaches every group and no page scrolls sideways (#191)', async ({ page }) => {
  const errors = collectErrors(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/${COLLECTION}`)
  await expect(page.getByRole('navigation', { name: 'Páginas de la competición' })).toHaveCount(0)      // no fixed sidebar on a phone
  await page.getByRole('button', { name: 'Abrir menú' }).click()
  const menu = page.getByRole('dialog', { name: 'Menú de navegación' })
  for (const group of ['Equipos', 'Jugadores', 'Partido', 'Live', 'Informes']) await expect(menu.getByRole('heading', { name: group })).toBeVisible()
  await menu.getByRole('link', { name: 'Posesiones' }).click()
  await expect(page).toHaveURL(new RegExp(`/${COLLECTION}/possessions$`))
  await expect(menu).toHaveCount(0)                                                                         // choosing a page closes the menu

  // the whole page fits 390 px: the document and the scrolling area of the page do not grow sideways
  const overflow = async () => page.evaluate(() => {
    const main = document.querySelector('main') as HTMLElement
    return { document: document.documentElement.scrollWidth - window.innerWidth, main: main.scrollWidth - main.clientWidth }
  })
  for (const path of ['', '/teams', '/possessions', '/players', '/lineups', '/comparativas', '/report', '/shots', '/predictive']) {
    await page.goto(`/${COLLECTION}${path}`)
    await page.waitForLoadState('networkidle')
    const { document: d, main } = await overflow()
    expect(d, `${path || 'resumen'}: the document grows sideways`).toBeLessThanOrEqual(0)
    expect(main, `${path || 'resumen'}: the page grows sideways`).toBeLessThanOrEqual(0)
  }
  expect(errors).toEqual([])
})

test('on a wide screen the competition can be changed from the header and the pages are in groups (#191)', async ({ page }) => {
  await page.goto(`/${COLLECTION}/teams`)
  const nav = page.getByRole('navigation', { name: 'Páginas de la competición' })
  await expect(nav.getByRole('heading', { name: 'Equipos' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Abrir menú' })).toHaveCount(0)
})

test('the API behind the page is healthy', async ({ request }) => {
  const live = await request.get('/api/v1/health')
  expect(await live.json()).toMatchObject({ status: 'ok' })
  const db = await request.get('/api/v1/health/db')
  expect(await db.json()).toMatchObject({ connected: true })
})
