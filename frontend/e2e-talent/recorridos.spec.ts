import { expect, test } from '@playwright/test'
import { ANA, enc, FBCYL_ALONE, FBCYL_LINKED, LF2_COMP, MY_TEAM, NO_SHOTS, open, serveTalent, WITH_SHOTS } from './support'

// The ways through Talent the staff takes, over the real publication of the exporter: search, profile and comparator, and the FBCYL player that IS a FEB person.
test.beforeEach(async ({ page }) => { await serveTalent(page) })

test.describe('navigation (#1007)', () => {
  test('the header takes you between the search and the comparator, and marks where you are', async ({ page }) => {
    await open(page, '/')
    const nav = page.getByRole('navigation', { name: 'Principal' })
    await expect(nav.getByRole('link', { name: 'Buscar' })).toHaveAttribute('aria-current', 'page')
    await nav.getByRole('link', { name: 'Comparar' }).click()
    await expect(page).toHaveURL(/\/comparar/)
    await expect(nav.getByRole('link', { name: 'Comparar' })).toHaveAttribute('aria-current', 'page')
    await nav.getByRole('link', { name: 'Buscar' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Buscador de jugadores' })).toBeVisible()
  })

  test('the comparison is still there when you come back to the comparator from the search', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)}`)
    const nav = page.getByRole('navigation', { name: 'Principal' })
    await nav.getByRole('link', { name: 'Buscar' }).click()
    await nav.getByRole('link', { name: 'Comparar' }).click()
    await expect(page.getByRole('table', { name: 'Comparación de jugadores' })).toBeVisible()
  })
})

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

test.describe('filters (#1008)', () => {
  test('on a phone the filters are closed behind a button and the first players are on the first screen', async ({ page }) => {
    await page.setViewportSize({ width: 412, height: 800 })
    await open(page, '/?s=2025')
    const toggle = page.getByRole('button', { name: /^Filtros/ })
    await expect(toggle).toBeVisible()
    await expect(page.getByRole('spinbutton', { name: 'Edad mínima' })).toBeHidden()
    await expect(page.getByLabel('Jugador o equipo')).toBeVisible()                  // the name stays: it is what is used most
    const first = await page.locator('a[href^="/jugador/"]').first().boundingBox()
    expect(first!.y).toBeLessThan(800)
    await toggle.click()
    await expect(page.getByRole('spinbutton', { name: 'Edad mínima' })).toBeVisible()
  })

  test('the active filters are chips that come off with a click, also with the panel closed', async ({ page }) => {
    await page.setViewportSize({ width: 412, height: 800 })
    await open(page, '/?s=2025&amin=60')
    await expect(page.getByRole('button', { name: 'Filtros (1)' })).toBeVisible()
    const chips = page.getByRole('list', { name: 'Filtros activos' })
    await expect(chips).toContainText('Edad: desde 60')
    await expect(page.getByText(/0 jugadores encontrados/)).toBeVisible()
    await chips.getByRole('button', { name: /Quitar el filtro Edad/ }).click()
    await expect(chips).toHaveCount(0)
    await expect(page.getByText(/[1-9]\d* jugadores? encontrad/)).toBeVisible()
  })

  test('on a desktop the filters are all in sight and there is no button to open them', async ({ page }) => {
    await open(page, '/?s=2025')
    await expect(page.getByRole('button', { name: /^Filtros/ })).toBeHidden()
    await expect(page.getByRole('spinbutton', { name: 'Edad mínima' })).toBeVisible()
  })

  test('the players are ticked in the list, a bar says how many and takes them to the comparator, and the choice survives the trip', async ({ page }) => {
    await open(page, '/?s=2025')
    await expect(page.getByRole('columnheader', { name: 'Comparar' })).toHaveCount(0)
    const boxes = page.getByRole('checkbox', { name: /^Comparar a / })
    await boxes.nth(0).check()
    await boxes.nth(1).check()
    const bar = page.getByRole('region', { name: 'Selección para comparar' })
    await expect(bar).toContainText('2 jugadores elegidos')
    await bar.getByRole('link', { name: /Comparar 2 jugadores/ }).click()
    await expect(page).toHaveURL(/\/comparar\?j=/)
    await expect(page.getByRole('table', { name: 'Comparación de jugadores' })).toBeVisible()
    await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Buscar' }).click()
    await expect(page.getByRole('region', { name: 'Selección para comparar' })).toContainText('2 jugadores elegidos')
  })

  test('with three ticked the rest are off', async ({ page }) => {
    await open(page, '/?s=2025')
    const boxes = page.getByRole('checkbox', { name: /^Comparar a / })
    for (const i of [0, 1, 2]) await boxes.nth(i).check()
    await expect(boxes.nth(3)).toBeDisabled()
    await expect(page.getByText(/Máximo 3 jugadores/)).toBeVisible()
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
    await expect(page.locator('svg [data-zone]').first()).toBeVisible()        // the court of Analytics with its bubbles (#1010)
  })

  test('lists the players most like him in his own competition and takes the staff to compare with one of them (#1010)', async ({ page }) => {
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    const list = page.getByRole('list', { name: 'Jugadores parecidos' })
    await expect(list.getByRole('listitem')).toHaveCount(5)
    await expect(list.getByRole('listitem').first()).toContainText('%')
    await list.getByRole('link', { name: /^Comparar con / }).first().click()
    await expect(page).toHaveURL(/\/comparar\?j=feb%3A10101%2C/)
    await expect(page.getByRole('table', { name: 'Comparación de jugadores' })).toBeVisible()
  })

  test('the navigation inside the profile takes you to each section and stays in sight (#1010)', async ({ page }) => {
    await page.setViewportSize({ width: 412, height: 700 })
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    const nav = page.getByRole('navigation', { name: 'En esta ficha' })
    await nav.getByRole('link', { name: 'Zonas de tiro' }).click()
    const zones = page.getByRole('heading', { name: 'Zonas de tiro' })
    await expect(zones).toBeInViewport()
    const below = await zones.boundingBox()
    const bar = await nav.boundingBox()
    expect(below!.y).toBeGreaterThanOrEqual(bar!.y + bar!.height - 1)          // the section is not hidden under the navigation
    await expect(nav).toBeInViewport()
    await nav.getByRole('link', { name: 'Datos personales' }).click()
    await expect(page.getByRole('heading', { name: 'Datos personales' })).toBeInViewport()
  })

  test('downloads the profile as a PDF named after the player, with the photo swapped for the initials (#1010)', async ({ page }) => {
    test.setTimeout(90_000)
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    await page.getByRole('button', { name: /Exportar/ }).click()
    await expect(page.getByRole('button', { name: 'CSV' })).toHaveCount(0)
    const download = page.waitForEvent('download', { timeout: 60_000 })
    await page.getByRole('button', { name: 'PDF' }).click()
    const file = await download
    expect(file.suggestedFilename()).toMatch(/^ficha-.*\.pdf$/)
    const path = await file.path()
    expect((await import('node:fs')).statSync(path!).size).toBeGreaterThan(5_000)
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

  test('shows the photo of FEB next to the name, and the initials when it does not load or the player has none (#1010)', async ({ page }) => {
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    await expect(page.locator('img[src*="foto.aspx?c=10101"]')).toBeVisible()
    await open(page, `/jugador/${enc(FBCYL_ALONE)}`)
    await expect(page.locator('img[src*="foto.aspx"]')).toHaveCount(0)
  })

  test('with the photo failing the profile shows initials, not a broken image (#1010)', async ({ page }) => {
    await serveTalent(page, { photos: false })
    await open(page, `/jugador/${enc(WITH_SHOTS)}`)
    await expect(page.locator('img[src*="foto.aspx"]')).toHaveCount(0)
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
    await expect(table.getByRole('columnheader')).toHaveCount(4)               // the label column, two players and the difference
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

  test('shows the difference between two players and offers to export the comparison (#1009)', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)}`)
    const table = page.getByRole('table', { name: 'Comparación de jugadores' })
    await expect(table.getByRole('columnheader', { name: 'Diferencia' })).toBeVisible()
    await page.getByRole('button', { name: /Exportar/ }).click()
    const download = page.waitForEvent('download')
    await page.getByRole('button', { name: 'CSV' }).click()
    expect((await download).suggestedFilename()).toMatch(/^comparacion-.*\.csv$/)
  })

  test('chooses the axes of the radar: hides one, moves another, and the choice survives a reload (#1014)', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)}`)
    const table = page.getByRole('table', { name: 'Comparación de jugadores' })
    await page.getByRole('checkbox', { name: /Tapones/ }).click()
    await expect(table.getByRole('rowheader', { name: /Tapones/ })).toHaveCount(0)
    await page.getByRole('button', { name: /Subir Asistencias/ }).click()
    await expect(page).toHaveURL(/ejes=ast/)
    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(table.getByRole('rowheader', { name: /Tapones/ })).toHaveCount(0)
    await page.getByRole('button', { name: /Restablecer los ejes/ }).click()
    await expect(table.getByRole('rowheader', { name: /Tapones/ })).toHaveCount(1)
    await expect(page).not.toHaveURL(/ejes=/)
  })

  test('keeps the list in the address, so reloading gives the same comparison', async ({ page }) => {
    await open(page, `/comparar?j=${enc(WITH_SHOTS)},${enc(NO_SHOTS)}`)
    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('table', { name: 'Comparación de jugadores' })).toBeVisible()
  })
})

test.describe('my team (#882)', () => {
  test('the staff chooses a competition and a team, sees the rotation, the holes of profile and the age, and the choice is remembered', async ({ page }) => {
    await open(page, '/mi-equipo')
    await expect(page.getByText('Elige tu equipo')).toBeVisible()
    await page.getByRole('combobox', { name: 'Competición' }).selectOption(LF2_COMP)
    const team = page.getByRole('combobox', { name: 'Equipo' })
    await expect(team.locator('option')).not.toHaveCount(1)
    await team.selectOption({ index: 1 })
    await expect(page.getByRole('table', { name: /Rotación de/ })).toBeVisible()
    await expect(page.getByRole('list', { name: 'Perfil de la rotación' }).getByRole('listitem')).toHaveCount(7)          // every axis (rebounds as one), with its best player
    await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Buscar' }).click()
    await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: 'Mi equipo' }).click()
    await expect(page.getByRole('table', { name: /Rotación de/ })).toBeVisible()          // it comes back with the team of last time
  })

  test('a hole is an axis nobody covers, not a position, and it opens the search with the filters already put (#882)', async ({ page }) => {
    await open(page, MY_TEAM)
    await expect(page.getByText('Hueco', { exact: true }).first()).toBeVisible()
    await expect(page.getByText(/el hueco se mide por el juego, no por la posición/)).toBeVisible()
    await page.getByRole('link', { name: /Buscar jugadores de/ }).first().click()
    await expect(page).toHaveURL(/p=75/)
    const chips = page.getByRole('list', { name: 'Filtros activos' })
    await expect(chips).toContainText('percentil 75')
    await expect(chips).toContainText('Solo con minutos suficientes')
  })

  test('a team that is not in the competition is said, not an empty page', async ({ page }) => {
    await open(page, `/mi-equipo?c=${enc(LF2_COMP)}&e=nadie`)
    await expect(page.getByText('No encontramos ese equipo')).toBeVisible()
  })
})
