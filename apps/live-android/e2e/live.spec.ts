import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import { FakeFeb } from '../src/feed/fakeFeb'

// the published-packages list must not depend on the real network (an offline error would add a second alert)
test.beforeEach(async ({ page }) => {
  await page.route('**/live-packages/**', route => route.fulfill({ json: { v: 1, packages: [] } }))
})

test('the demo opens on the latest recorded match, local team on the left, and alerts show up (issue #223)', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))

  await page.goto('/')
  await expect(page.getByText('RECOLETAS ZAMORA').first()).toBeVisible({ timeout: 90_000 })
  await expect(page.getByText('MIPELLETYMAS B.F. LEON').first()).toBeVisible()
  // Zamora hosted Leon: the local team goes on the left, ours is marked
  await expect(page.locator('.scoreboard .team').nth(0)).toContainText('RECOLETAS ZAMORA')
  await expect(page.locator('.scoreboard .team').nth(1)).toContainText('MIPELLETYMAS B.F. LEON')
  await expect(page.locator('.scoreboard .team').nth(1)).toContainText('Tu equipo')

  await page.getByRole('radio', { name: '60×' }).click()
  await page.getByRole('button', { name: 'Reproducir' }).click()

  // the first alerts of the real match come a few minutes after tip-off (about 10 s at 60x)
  await expect(page.locator('.alert').first()).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.clock')).not.toHaveText('Q1 10:00')

  // the pace card (issue #209) leaves "calculando" and shows the projected total computed by the real engine
  await expect(page.locator('.pace-card')).toContainText('posesiones por equipo', { timeout: 30_000 })

  expect(errors).toEqual([])
})

test('the sample game is still there as the last option of the selector', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })
  await page.getByLabel('Partido de la demostración').selectOption('sample')
  await expect(page.getByText('ACEITES ABRIL ADBA SANFER').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('MANRESA CBF A').first()).toBeVisible()
})

test('layout fits a phone: no horizontal scroll and touch-sized controls', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)

  for (const button of await page.getByRole('button').all()) {
    const box = await button.boundingBox()
    expect(box!.height).toBeGreaterThanOrEqual(44)
  }
})

test('the engine update stays fluid (well under a second per update on this machine)', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Reproducir' }).click({ timeout: 90_000 })
  const perf = page.locator('.perf')
  await expect(perf).toBeVisible({ timeout: 30_000 })
  const ms = Number((await perf.textContent())!.replace(/\D/g, ''))
  expect(ms).toBeLessThan(1000)
})

test('importing an encrypted package in a real browser: WebCrypto + engine validation + persistence', async ({ page }) => {
  const bpkg = fileURLToPath(new URL('../../../tests/live_vectors/demo.bpkg', import.meta.url))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })

  // the import is in the Paquetes tab (issue #224)
  await page.getByRole('tab', { name: 'Paquetes' }).click()

  // wrong password first: a clear error and nothing stored
  await page.getByLabel('Fichero del paquete (.bpkg)').setInputFiles(bpkg)
  await page.getByLabel('Contraseña del paquete').fill('contraseña-incorrecta')
  await page.getByRole('button', { name: 'Importar' }).click()
  await expect(page.getByRole('alert')).toContainText('contraseña')

  await page.getByLabel('Contraseña del paquete').fill('clave-de-prueba-1')
  await page.getByRole('button', { name: 'Importar' }).click()
  await expect(page.getByText(/partidos: 1 propios/)).toBeVisible({ timeout: 30_000 })   // the summary of the loaded package

  // survives a reload (IndexedDB) and can be removed
  await page.reload()
  await expect(page.getByText(/partidos: 1 propios/)).toBeVisible({ timeout: 90_000 })   // the tab is remembered too
  await page.getByRole('button', { name: 'Quitar paquete' }).click()
  await page.getByRole('tab', { name: 'Partido' }).click()
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 30_000 })
})

test('the real recorded match (Zamora - Leon) plays through the real engine in a real browser (issue #174)', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })

  await expect(page.getByText('MIPELLETYMAS B.F. LEON').first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('RECOLETAS ZAMORA').first()).toBeVisible()

  await page.getByRole('radio', { name: '300×' }).click()
  await page.getByRole('button', { name: 'Reproducir' }).click()
  // 7156 s of feed at 300x: ~25 s. The official result, with the corrected lines of the real feed applied
  await expect(page.getByText('Partido finalizado')).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.scoreboard .pts').nth(0)).toHaveText('59') // Zamora, local, on the left
  await expect(page.locator('.scoreboard .pts').nth(1)).toHaveText('38') // Leon, visitor
  await expect(page.locator('.alert').first()).toBeVisible()
  // one chronological flow, the latest on top, 20 visible and the older ones collapsed (#313); the header counts per level (#229)
  await expect(page.locator('.alert-counts')).toContainText(/\d+ críticas?/) // exact counts depend on the rules and the playback speed
  await expect(page.locator('.alert-counts')).toContainText(/\d+ avisos/) // exact counts depend on the playback speed
  await expect(page.locator('.alert-counts')).toContainText(/\d+ informativas/)
  await expect(page.locator('.alert-list > .alerts > li')).toHaveCount(20)
  await expect(page.locator('.alerts-older > summary')).toContainText(/Ver las \d+ anteriores/)
  await expect(page.locator('.alerts-older')).not.toHaveAttribute('open', '')
  await page.screenshot({ path: 'test-results/alerts-hierarchy.png', fullPage: true })
  await expect(page.locator('.pace-card')).toContainText('posesiones por equipo')
  await expect(page.locator('.wp-card')).toContainText(/\d+ %/) // the win probability, experimental (#257)

  expect(errors).toEqual([])
})

test('the win probability card in the middle of the real match, for the layout review (issue #257)', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })
  await expect(page.getByText('MIPELLETYMAS B.F. LEON').first()).toBeVisible({ timeout: 60_000 })
  await page.getByRole('radio', { name: '300×' }).click()
  await page.getByRole('button', { name: 'Reproducir' }).click()
  await page.waitForTimeout(9_000) // ~ the second quarter at 300x
  await page.getByRole('button', { name: 'Pausa' }).click()
  const card = page.getByRole('region', { name: 'Probabilidad de victoria' })
  await expect(card).toContainText(/\d+ %/)
  await expect(card).toContainText('Experimental')
  await card.screenshot({ path: 'test-results/win-prob-card.png' })
  await page.screenshot({ path: 'test-results/win-prob-screen.png', fullPage: true })
})

test('live mode: connects to a (fake) FEB serving the real recording and follows the match in a real browser (issue #217)', async ({ page }) => {
  test.setTimeout(180_000)
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))

  // the package of the match is already on the device (what "Importar" / "Descargar" leave in IndexedDB)
  const pkg = fs.readFileSync(fileURLToPath(new URL('../../../tests/recordings/2524470.package.json', import.meta.url)), 'utf8')
  await page.addInitScript(plaintext => {
    const open = indexedDB.open('basketlab-live', 1)
    open.onupgradeneeded = () => open.result.createObjectStore('package')
    open.onsuccess = () => open.result.transaction('package', 'readwrite').objectStore('package')
      .put({ plaintext, savedAt: new Date().toISOString() }, 'current')
  }, pkg)

  // a fake FEB: the real recording played 240x faster, behind the same addresses, token and CORS rules
  const recording = JSON.parse(fs.readFileSync(fileURLToPath(new URL('../public/demo/2524470.recording.json', import.meta.url)), 'utf8'))
  const feb = new FakeFeb(recording)
  const startedAt = Date.now()
  const SPEED = 240
  await page.route(/https:\/\/(baloncestoenvivo|intrafeb)\.feb\.es\/.*/, async route => {
    const cors = { 'access-control-allow-origin': '*', 'access-control-allow-headers': 'authorization, accept, accept-language' }
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: cors })
    feb.at = 5 + ((Date.now() - startedAt) / 1000) * SPEED
    const auth = route.request().headers().authorization
    const response = await feb.get(route.request().url(), auth ? { Authorization: auth } : {})
    await route.fulfill({ status: response.status, headers: { ...cors, 'content-type': 'application/json' }, body: response.text })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Conectar con FEB' }).click({ timeout: 90_000 })
  await expect(page.getByText(/En directo · último dato/)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('MIPELLETYMAS B.F. LEON').first()).toBeVisible()

  // the whole match (7156 s of feed at 240x = 30 s) and the late final status: the official result
  await expect(page.getByText('Partido finalizado')).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('.scoreboard .pts').nth(0)).toHaveText('59') // Zamora, local, on the left
  await expect(page.locator('.scoreboard .pts').nth(1)).toHaveText('38') // Leon, visitor
  await expect(page.locator('.alert').first()).toBeVisible()

  expect(errors).toEqual([])
})

test('light and dark: the switch in the header changes the whole screen and is remembered (issue #322)', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })
  const background = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  const toggle = () => page.getByRole('button', { name: /^cambiar a modo/i })
  const first = await background()                                      // the system theme of the browser (light in Playwright)
  await page.screenshot({ path: 'test-results/theme-system.png' })
  await toggle().click()
  const other = await background()
  expect(other).not.toBe(first)
  const chosen = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
  expect(['light', 'dark']).toContain(chosen)
  await page.screenshot({ path: `test-results/theme-${chosen}.png` })
  await page.reload()
  await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })
  expect(await background()).toBe(other)                                  // remembered across a reload
  await toggle().click()
  expect(await background()).toBe(first)
})
