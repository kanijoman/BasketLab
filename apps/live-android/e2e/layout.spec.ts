import { expect, test, type Page } from '@playwright/test'
import { collectBoxes, layoutProblems } from '../src/test/layoutCheck'

// Issue #508: the styles of the new screens used to be discovered on the tablet (a button over the name of the teams, texts on one line that stick out).
// Every tab of the app is opened with long names and checked on a phone and on a narrow phone: nothing leaves the screen, no text or button sits on another one.

const long = (name: string) => `${name} CLUB DE BALONCESTO DEPORTIVO UNIVERSIDAD`
const side = (id: string, name: string) => ({ id, name })
const INDEX = {
  v: 1, packages: [], open_key: null, rounds: [
    { collection: 'SEGUNDA_FEB_2026_2027_Liga_Regular_A', round: 4, file: 'rounds/a.bpkgz', sha256: 'x', bytes: 1000, club: false,
      competition: { key: 'k', label: 'SEGUNDA FEB · Liga Regular "A"', competition: 'SEGUNDA FEB', group: 'Liga Regular "A"', season: '2026/2027', league: 'FEB', level: 3, gender: 'M' },
      matches: [
        { code: '1', start: '2030-10-24T19:30', home: side('1', long('CULTURAL Y DEPORTIVA LEONESA')), away: side('2', long('ZAMORA')), own_id: '1', own_ids: ['1', '2'], is_club: false },
        { code: '2', start: '2030-10-24T18:00', home: side('3', 'GETAFE'), away: side('4', 'TOLEDO'), own_id: '3', own_ids: ['3', '4'], is_club: true },
      ] },
  ],
}

/** Opens the dropdown of the app (issue #571) and chooses the option with that value. */
async function choose(page: Page, label: string, value: string) {
  await page.getByRole('combobox', { name: label }).click()
  await page.locator(`[role="option"][data-value="${value}"]`).click()
}

async function open(page: Page, width: number) {
  await page.setViewportSize({ width, height: 800 })
  await page.route('**/live-packages/**', route => route.fulfill({ json: INDEX }))
  await page.goto('/')
  await page.getByRole('tab', { name: 'Partido', exact: true }).click({ timeout: 90_000 })
}

async function problems(page: Page, width: number): Promise<string[]> {
  const boxes = await page.evaluate(collectBoxes)
  return layoutProblems(boxes, width)
}

for (const width of [412, 320]) {
  test(`every tab fits a phone of ${width} px: nothing sticks out and nothing overlaps (issue #508)`, async ({ page }) => {
    await open(page, width)
    const found: string[] = []
    const check = async (where: string) => found.push(...(await problems(page, width)).map(p => `${where}: ${p}`))
    // the page must not be wider than the screen (a scrolled table must not stretch it) and the fixed bar of tabs, which the geometry check leaves out, must fit
    const fits = async (where: string) => {
      const wide = await page.evaluate(() => document.documentElement.scrollWidth)
      if (wide > width + 2) found.push(`${where}: la página es más ancha que la pantalla (${wide} > ${width})`)
      const bar = await page.getByRole('tablist', { name: 'Secciones' }).boundingBox()
      if (!bar || bar.x < -1 || bar.x + bar.width > width + 1) found.push(`${where}: la barra de pestañas se sale de la pantalla (${JSON.stringify(bar)})`)
      for (const tab of await page.getByRole('tab').all()) {
        const box = await tab.boundingBox()
        if (box && box.x + box.width > width + 1) found.push(`${where}: la pestaña «${await tab.textContent()}» se sale de la pantalla`)
      }
    }

    await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })
    await check('Partido')

    // Boxscore (#593): the table moves sideways inside its own box, so the box, the controls and the names must fit; the name of the player stays when it is moved
    await page.getByRole('radio', { name: '300×' }).click()
    await page.getByRole('button', { name: 'Reproducir' }).click()
    await page.getByRole('tab', { name: 'Boxscore' }).click()
    await expect(page.locator('.bx-table tbody tr').first()).toBeVisible({ timeout: 30_000 })
    await check('Boxscore / propio')
    await fits('Boxscore / propio')
    await page.getByRole('radio', { name: 'Avanzada' }).click()
    await check('Boxscore / avanzada')
    await fits('Boxscore / avanzada')
    await page.getByRole('radiogroup', { name: 'Equipo' }).getByRole('radio').nth(1).click()
    await check('Boxscore / el otro equipo')
    await fits('Boxscore / el otro equipo')
    const scroll = page.locator('.bx-scroll')
    await scroll.evaluate(el => { el.scrollLeft = 10_000 })
    const [area, name] = [await scroll.boundingBox(), await page.locator('.bx-table tbody .bx-name').first().boundingBox()]
    if (!area || !name || Math.abs(name.x - area.x) > 2) found.push(`Boxscore: el nombre del jugador no se queda fijo al mover la tabla (${JSON.stringify({ area, name })})`)
    await page.getByRole('tab', { name: 'Partido', exact: true }).click()

    await page.getByRole('tab', { name: 'Partidos' }).click()
    await expect(page.getByRole('combobox', { name: 'Tipo de partido' })).toBeVisible()
    await expect(page.getByText(/CULTURAL Y DEPORTIVA LEONESA/).first()).toBeVisible({ timeout: 30_000 })
    await check('Partidos / En directo')
    // an open dropdown stays inside the screen, whatever the length of its options (it floats over the list on purpose, so it is not part of the overlap check)
    await page.getByRole('combobox', { name: 'Competición' }).click()
    const list = await page.getByRole('listbox').boundingBox()
    if (!list || list.x < 0 || list.x + list.width > width) found.push(`Desplegable de competición: sale de la pantalla (${JSON.stringify(list)})`)
    await page.getByRole('option', { name: 'SEGUNDA FEB' }).click()
    await check('Partidos / En directo, filtrado')

    await choose(page, 'Tipo de partido', 'demo')
    await check('Partidos / Demos')

    await choose(page, 'Tipo de partido', 'finished')
    await check('Partidos / Finalizados')

    await page.getByRole('tab', { name: 'Acerca de' }).click()
    await check('Acerca de')

    expect(found).toEqual([])
  })
}
