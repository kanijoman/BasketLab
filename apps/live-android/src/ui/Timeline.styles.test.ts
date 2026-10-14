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

  it('shows the informative alerts as a block with a heading, not behind a summary', () => {
    expect(css).not.toContain('.alerts-info > summary')
    expect(rule('.alerts-info > h3')).toContain('font-size')
  })
})
