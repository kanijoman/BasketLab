import { test } from '@playwright/test'

// Issue #197 (U7): captures of the key pages in both themes at the three widths of the design (390, 768, 1280). They are not compared yet (the baselines are generated
// on Linux when the pages settle); the CI keeps them as an artifact (`web-visual-captures`) so a change of look can be reviewed in the pull request.
const C = 'L_F_-2_2025_2026_Liga_Regular_B'
const PAGES: [string, string][] = [['home', '/'], ['summary', `/${C}`], ['teams', `/${C}/teams`], ['players', `/${C}/players`], ['shots', `/${C}/shots`], ['pbp', `/${C}/pbp`]]

for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 768, 1280]) {
    test(`captures: ${theme}, ${width} px`, async ({ page }, info) => {
      await page.addInitScript(t => localStorage.setItem('basketlab-web-theme', t), theme)
      await page.setViewportSize({ width, height: 900 })
      for (const [name, path] of PAGES) {
        await page.goto(path)
        await page.waitForLoadState('networkidle')
        await page.screenshot({ path: info.outputPath(`${name}-${theme}-${width}.png`), fullPage: true })
      }
    })
  }
}
