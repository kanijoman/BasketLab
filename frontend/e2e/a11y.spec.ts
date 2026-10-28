import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

// Issue #197 (U7): accessibility of the key pages, in both themes and on a phone and a desktop (WCAG 2.0/2.1 A and AA: contrast, names of the controls, keyboard
// access to what scrolls). A violation names the rule, the element and the colours: the audit of 28/10/2026 found 197 of them before the fixes.
const C = 'L_F_-2_2025_2026_Liga_Regular_B'
const PAGES = ['/', `/${C}`, `/${C}/teams`, `/${C}/players`, `/${C}/shots`, `/${C}/lineups`, `/${C}/report`, `/${C}/team-report`, `/${C}/predictive`, `/${C}/matches`, `/${C}/comparativas`]

for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 1280]) {
    test(`no accessibility violations: ${theme}, ${width} px`, async ({ page }) => {
      test.setTimeout(180_000)
      await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
      await page.setViewportSize({ width, height: 800 })
      const found: string[] = []
      for (const path of PAGES) {
        await page.goto(path)
        await page.waitForLoadState('networkidle')
        const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
        for (const v of result.violations) {
          for (const n of v.nodes.slice(0, 2)) found.push(`${path} · ${v.id} (${v.impact}): ${n.target.join(' ')} — ${(n.any[0]?.message ?? '').slice(0, 120)}`)
        }
      }
      expect(found).toEqual([])
    })
  }
}

test('with reduced motion asked for, nothing animates for long (spinners, transitions, page changes)', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/${C}/teams`)
  const longest = await page.evaluate(() => {
    const seconds = (v: string) => Math.max(0, ...v.split(',').map(s => (s.trim().endsWith('ms') ? parseFloat(s) / 1000 : parseFloat(s)) || 0))
    return Math.max(0, ...[...document.querySelectorAll('*')].map(el => {
      const s = getComputedStyle(el)
      return Math.max(seconds(s.animationDuration), seconds(s.transitionDuration))
    }))
  })
  expect(longest).toBeLessThanOrEqual(0.01)
})
