import { expect, test } from '@playwright/test'
import { ANA, enc, open, serveTalent } from './support'

// What Talent says when the data is not what it expects: nothing published, a competition that does not open, nobody with that id. Never a blank page or an endless spinner.
test('nothing published yet: the search, the profile and the comparator say so', async ({ page }) => {
  await serveTalent(page, { missing: p => p === 'index.json' })
  for (const path of ['/', `/jugador/${enc(ANA)}`, '/comparar']) {
    await open(page, path)
    await expect(page.getByText(/Aún no hay datos de jugadores publicados/)).toBeVisible()
  }
})

test('a competition that fails does not hide the others: the search says which one could not be opened', async ({ page }) => {
  await serveTalent(page, { broken: p => /^players\/feb~7Clf2/.test(p) })
  await open(page, '/?s=2025')
  await expect(page.getByText(/No se ha podido abrir/).first()).toBeVisible()
})

test('a player that does not exist: the profile says it and offers the way back', async ({ page }) => {
  await serveTalent(page)
  await open(page, `/jugador/${enc('feb:no-existe')}`)
  await expect(page.getByText('No encontramos a este jugador')).toBeVisible()
  await page.getByRole('link', { name: 'Volver al buscador' }).click()
  await expect(page).toHaveURL(/\/$/)
})

test('the zones file is missing: the profile says so and the rest of it still works', async ({ page }) => {
  await serveTalent(page, { missing: p => p.includes('zones') })
  await open(page, `/jugador/${enc(ANA)}`)
  await expect(page.getByText('Esta competición no tiene datos de zonas publicados.')).toBeVisible()
  await expect(page.getByRole('img', { name: /Perfil de/ })).toBeVisible()
})

test('a player of the address that does not exist is named in the comparator', async ({ page }) => {
  await serveTalent(page)
  await open(page, `/comparar?j=${enc(ANA)},${enc('feb:no-existe')}`)
  await expect(page.getByRole('alert')).toContainText('feb:no-existe')
})

test('any other address goes to the search', async ({ page }) => {
  await serveTalent(page)
  await open(page, '/no/existe')
  await expect(page.getByRole('heading', { level: 1, name: 'Buscador de jugadores' })).toBeVisible()
})
