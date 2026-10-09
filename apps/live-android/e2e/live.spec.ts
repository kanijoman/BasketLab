import { expect, test } from '@playwright/test'

test('the demo runs on a phone viewport: Pyodide boots in a worker and alerts show up', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))

  await page.goto('/')
  await expect(page.getByText('ACEITES ABRIL ADBA SANFER')).toBeVisible({ timeout: 90_000 })
  await expect(page.getByText('MANRESA CBF A')).toBeVisible()

  await page.getByLabel('Velocidad').selectOption('60')
  await page.getByRole('button', { name: 'Reproducir' }).click()

  // game second ~1200 (≈20 s at 60x) already has team-foul alerts in the reference game
  await expect(page.locator('.alert').first()).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.clock')).not.toHaveText('Q1 10:00')

  expect(errors).toEqual([])
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
