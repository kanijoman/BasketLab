import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { open, PAGES, serveTalent } from './support'

// Accessibility of every page of Talent in both themes, on a phone and on a desktop (WCAG 2.0/2.1 A and AA: contrast, names of the controls, keyboard access to what scrolls), as the rest of the web (#197).
for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 1280]) {
    test(`no accessibility violations: ${theme}, ${width} px`, async ({ page }) => {
      test.setTimeout(180_000)
      await serveTalent(page)
      await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
      await page.setViewportSize({ width, height: 800 })
      const found: string[] = []
      for (const [name, path] of PAGES) {
        await open(page, path)
        const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
        for (const v of result.violations) {
          for (const n of v.nodes.slice(0, 2)) found.push(`${name} · ${v.id} (${v.impact}): ${n.target.join(' ')} — ${(n.any[0]?.message ?? '').slice(0, 120)}`)
        }
      }
      expect(found).toEqual([])
    })
  }
}
