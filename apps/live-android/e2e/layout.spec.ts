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

    await expect(page.getByRole('button', { name: 'Reproducir' })).toBeVisible({ timeout: 90_000 })
    await check('Partido')

    await page.getByRole('tab', { name: 'Partidos' }).click()
    await expect(page.getByLabel('Tipo de partido')).toBeVisible()
    await expect(page.getByText(/CULTURAL Y DEPORTIVA LEONESA/).first()).toBeVisible({ timeout: 30_000 })
    await check('Partidos / En directo')
    await page.getByLabel('Competición').selectOption('SEGUNDA FEB')
    await check('Partidos / En directo, filtrado')

    await page.getByLabel('Tipo de partido').selectOption('demo')
    await check('Partidos / Demos')

    await page.getByLabel('Tipo de partido').selectOption('finished')
    await check('Partidos / Finalizados')

    await page.getByRole('tab', { name: 'Acerca de' }).click()
    await check('Acerca de')

    expect(found).toEqual([])
  })
}
