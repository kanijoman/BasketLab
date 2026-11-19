import { expect, test } from '@playwright/test'
import { ANA, enc, FBCYL_ALONE, FBCYL_LINKED, NO_SHOTS, open, serveTalent, WITH_SHOTS } from './support'

// The ways through Talent the staff takes, over the real publication of the exporter: search, profile and comparator, and the FBCYL player that IS a FEB person.
test.beforeEach(async ({ page }) => { await serveTalent(page) })

test.describe('search', () => {
  test('opens on the latest season, says how many players and finds one by name', async ({ page }) => {
    await open(page, '/')
    await expect(page.getByRole('heading', { level: 1, name: 'Buscador de jugadores' })).toBeVisible()
    await expect(page.getByText(/36 jugadores encontrados/)).toBeVisible()
    await page.getByLabel('Jugador o equipo').fill('alfa00')
    await expect(page.getByText(/1 jugador encontrado/)).toBeVisible()
    await expect(page.getByRole('link', { name: /JUGADOR00 ALFA00 PEREZ/ }).first()).toBeVisible()
  })

  test('says no player when no filter lets anyone through', async ({ page }) => {
    await open(page, '/?s=2025')
    await page.getByRole('spinbutton', { name: 'Edad mínima' }).fill('60')
    await expect(page.getByText(/0 jugadores encontrados/)).toBeVisible()
    await expect(page.getByText('Ningún jugador cumple los filtros.')).toBeVisible()
  })

  test('opens the profile of a player from the list', async ({ page }) => {
    await open(page, '/?s=2025')
    await page.getByRole('link', { name: /^(ANA PRUEBA UNO|J1\. ALPHA)$/ }).first().click()
    await expect(page).toHaveURL(/\/jugador\//)
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  })
})

test.describe('profile', () => {
  test('has the bio, the trajectory, the radar with its numbers and the shots by zone', async ({ page }) => {
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    await expect(page.getByRole('heading', { name: 'Datos personales' })).toBeVisible()
    await expect(page.getByRole('img', { name: /Perfil de/ })).toBeVisible()
    await expect(page.getByRole('list', { name: 'Percentiles' }).getByRole('listitem')).toHaveCount(8)
    const zones = page.getByRole('table', { name: 'Tiros por zona' })
    await expect(zones).toBeVisible()
    await expect(zones.getByRole('row')).toHaveCount(12)                       // header, ten zones and the total
  })

  test('says there are no shots when the file has none of the player, and draws no table of zeros', async ({ page }) => {
    await open(page, `/jugador/${enc(NO_SHOTS)}`)
    await expect(page.getByText(/Sin tiros registrados/)).toBeVisible()
    await expect(page.getByRole('table', { name: 'Tiros por zona' })).toHaveCount(0)
  })

  test('the FBCYL player linked to a FEB person is sent to her profile, with the FBCYL season in her trajectory', async ({ page }) => {
    await open(page, `/jugador/${enc(FBCYL_LINKED)}`)
    await expect(page).toHaveURL(new RegExp(`/jugador/${enc(ANA)}$`))
    await expect(page.getByRole('heading', { level: 1, name: /ANA PRUEBA UNO/ })).toBeVisible()
    await expect(page.getByText('Enlazada de FBCYL').first()).toBeVisible()
  })

  test('a FBCYL player nobody links has her own profile, with what is missing shown as a dash', async ({ page }) => {
    await open(page, `/jugador/${enc(FBCYL_ALONE)}`)
    await expect(page).toHaveURL(new RegExp(`/jugador/${enc(FBCYL_ALONE)}$`))
    await expect(page.getByTitle('Sin dato').first()).toBeVisible()
  })

  test('goes to the comparator with the player already chosen', async ({ page }) => {
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    await page.getByRole('link', { name: /Comparar con otros jugadores/ }).click()
    await expect(page).toHaveURL(/\/comparar\?j=/)
    await expect(page.getByRole('list', { name: 'Jugadores elegidos' }).getByRole('listitem')).toHaveCount(1)
  })
})

test.describe('comparator', () => {
  test('adds a player by name, shows both side by side and takes one out', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)}`)
    await page.getByRole('searchbox', { name: 'Añadir jugador' }).fill('bea')
    await page.getByRole('button', { name: /BEA PRUEBA DOS/ }).click()
    const table = page.getByRole('table', { name: 'Comparación de jugadores' })
    await expect(table).toBeVisible()
    await expect(table.getByRole('columnheader')).toHaveCount(3)               // the label column and two players
    await expect(page.getByText(/nunca se compara entre competiciones/)).toBeVisible()
    await page.getByRole('button', { name: /Quitar BEA PRUEBA DOS/ }).click()
    await expect(table).toHaveCount(0)
    await expect(page.getByText('Elige de dos a tres jugadores')).toBeVisible()
  })

  test('compares players of different leagues and stops at three', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)},${enc(FBCYL_ALONE)}`)
    const table = page.getByRole('table', { name: 'Comparación de jugadores' })
    await expect(table.getByRole('columnheader')).toHaveCount(4)
    await expect(table.getByText(/Primera Nacional Femenina/).first()).toBeVisible()
    await expect(page.getByRole('searchbox', { name: 'Añadir jugador' })).toBeDisabled()
    await expect(page.getByText(/Ya hay 3 jugadores/)).toBeVisible()
  })

  test('keeps the list in the address, so reloading gives the same comparison', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)}`)
    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('table', { name: 'Comparación de jugadores' })).toBeVisible()
  })
})
