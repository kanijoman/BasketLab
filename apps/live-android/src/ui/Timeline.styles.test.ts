import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

function rule(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

// Issue #309: a vertical swipe over the timeline must scroll the page, not drag the thumb and jump the match.
describe('timeline touch behaviour (issue #309)', () => {
  it('lets a vertical swipe scroll the page', () => {
    expect(rule(".timeline input[type='range']")).toContain('touch-action: pan-y')
  })

  it('the older alerts wait behind a summary, and the informative ones have no block of their own any more (#313)', () => {
    expect(css).not.toContain('.alerts-info')
    expect(rule('.alerts-older > summary')).toContain('min-height: 44px')
  })
})

// Issue #336: the help text pushed the radio buttons of the alert modes into one running line (Conservador after Medio)
describe('alert mode options (issue #336)', () => {
  it('are one row each: the radio on the left, the name and its help stacked on the right', () => {
    expect(rule('.alert-mode label')).toMatch(/display: grid/)
    expect(rule('.alert-mode label')).toMatch(/grid-template-columns: auto 1fr/)
    expect(rule('.alert-mode label')).toMatch(/min-height: 44px/)
    expect(rule('.alert-mode .detail')).toMatch(/display: block/)
  })
})

// Issue #322: the e2e of the phone layout wants every button at least 44 px tall; the new switch and counters must not be smaller
describe('touch size of the controls added in #322', () => {
  it('the theme switch and the severity counters are at least 44 px', () => {
    expect(rule('.brand-header .theme-toggle')).toMatch(/height: 44px/)
    expect(rule('button.count')).toMatch(/min-height: 44px/)
  })
})
