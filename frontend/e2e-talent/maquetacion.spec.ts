import { expect, test } from '@playwright/test'
import { open, PAGES, serveTalent, WIDTHS } from './support'

// The layout of every page of Talent on a small phone (320), a phone (412) and a desktop (1280): the page never scrolls sideways and nothing sticks out of the screen except what scrolls on
// purpose (a table in its own scrolling region). It is what was checked by hand in #1004: a screen-reader-only text stretched the page of the comparator, a table showed two columns.
test.beforeEach(async ({ page }) => { await serveTalent(page) })

for (const width of WIDTHS) {
  for (const [name, path] of PAGES) {
    test(`${name} fits in ${width} px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await open(page, path)
      const { scroll, client } = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }))
      expect(scroll, 'the page scrolls sideways').toBeLessThanOrEqual(client)
      const outside = await page.evaluate(() => {
        const vw = document.documentElement.clientWidth
        const scrolls = (e: Element) => { const o = getComputedStyle(e).overflowX; return o === 'auto' || o === 'scroll' }
        return [...document.querySelectorAll('body *')].filter(e => {
          const r = e.getBoundingClientRect()
          if (r.width === 0 || r.right <= vw + 1) return false
          for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) if (scrolls(p) && p.getBoundingClientRect().right <= vw + 1) return false     // inside a region that scrolls
          return true
        }).slice(0, 5).map(e => `${e.tagName}.${String(e.className).slice(0, 40)}`)
      })
      expect(outside, 'elements that stick out of the screen').toEqual([])
    })
  }
}

test('a very long name typed in the search does not break the layout on a phone', async ({ page }) => {
  await serveTalent(page)
  await page.setViewportSize({ width: 320, height: 900 })
  await open(page, '/')
  await page.getByLabel('Jugador o equipo').fill('ANA BEATRIZ DEL CARMEN DE LOS ÁNGELES FERNÁNDEZ DE LA VEGA-RODRÍGUEZ SANTAMARÍA')
  const { scroll, client } = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }))
  expect(scroll).toBeLessThanOrEqual(client)
})

test('the table of the comparator that scrolls sideways is a region the keyboard can reach', async ({ page }) => {
  await serveTalent(page)
  await page.setViewportSize({ width: 320, height: 900 })
  await open(page, PAGES.find(([n]) => n === 'comparador')![1])
  const region = page.getByRole('region', { name: /Tabla de comparación/ })
  await region.focus()
  await expect(region).toBeFocused()
})

test('the bar of the players ticked to compare fits on a phone and does not cover the list for good', async ({ page }) => {
  await serveTalent(page)
  await page.setViewportSize({ width: 320, height: 700 })
  await open(page, '/?s=2025')
  const boxes = page.getByRole('checkbox', { name: /^Comparar a / })
  for (const i of [0, 1, 2]) await boxes.nth(i).check()
  const bar = page.getByRole('region', { name: 'Selección para comparar' })
  await expect(bar).toBeVisible()
  const { scroll, client } = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }))
  expect(scroll).toBeLessThanOrEqual(client)
  const box = await bar.boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(320)
})
