import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, '..', 'styles.css'), 'utf8')

/** The declarations of the first rule whose selector is exactly ``selector`` ('' when there is none). */
function rule(selector: string): string {
  const start = css.indexOf(`\n${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

// Regression (#210): the "Próximos partidos" panel used a class with no CSS: default bullets, and the rival, the date and
// the Descargar button stuck together and badly aligned.
describe('styles of the published packages list (issue #210)', () => {
  it('has no bullets and no default padding', () => {
    const list = rule('.remote-packages')
    expect(list).toContain('list-style: none')
    expect(list).toContain('padding: 0')
  })

  it('shows each package as a card with the match on the left and the button on the right', () => {
    const item = rule('.remote-packages li')
    expect(item).toContain('display: flex')
    expect(item).toContain('justify-content: space-between')
    expect(item).toContain('align-items: center')
    expect(item).toContain('border')
    expect(item).toContain('gap')
  })

  it('lets the text wrap and keeps the button from shrinking, so a narrow phone does not scroll sideways', () => {
    expect(rule('.remote-packages li > span')).toContain('min-width: 0')
    expect(rule('.remote-packages li button')).toContain('flex: none')
  })

  it('styles the password field of the panel like the other inputs of the app', () => {
    const field = rule('.remote-packages-pass input')
    expect(field).toContain('min-height: 44px')
    expect(rule('.remote-packages-pass')).toContain('display: grid')
  })

  // Regression (#404): "Seguir como <equipo>" overflowed the card with a long team name: the buttons had no way to shrink or wrap.
  it('lets the "Seguir como" buttons shrink and wrap a long team name inside the card', () => {
    const sides = rule('.round-sides')
    expect(sides).toContain('min-width: 0')
    const button = rule('.remote-packages li.round-match .round-sides button')
    expect(button).toContain('min-width: 0')
    expect(button).toContain('overflow-wrap: anywhere')
    expect(button).toContain('height: auto')
    expect(rule('.remote-packages li.round-match')).toContain('min-width: 0')
  })
})
