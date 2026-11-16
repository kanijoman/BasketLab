import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

function rule(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

// Issue #933: the bin joined the head of the card (severity, category, time); on a phone of 320 px they do not fit in one row, so the head wraps instead of
// pushing the time over the bin. The target of the bin is a finger's (44 px: the .icon-button of the app).
describe('the head of an alert with the dismiss button (issue #933)', () => {
  it('wraps when badge, category, time and bin do not fit a narrow phone', () => {
    expect(rule('.alert-head')).toContain('flex-wrap: wrap')
  })

  it('the bin is an icon button of 44 px, and the time keeps the right edge', () => {
    expect(rule('.icon-button')).toContain('width: 44px')
    expect(rule('.alert-head .alert-time')).toContain('margin-left: auto')
  })
})
