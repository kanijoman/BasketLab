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

  it('shows each package as a card with the text on top and the buttons under it, never one on the other (issue #507)', () => {
    const item = rule('.remote-packages li')
    expect(item).toContain('display: grid')
    expect(item).toContain('border')
    expect(item).toContain('gap')
    expect(item).toContain('min-width: 0')
  })

  it('lets the text wrap and the buttons shrink and wrap, so a narrow phone does not scroll sideways', () => {
    expect(rule('.remote-packages li > span')).toContain('min-width: 0')
    expect(rule('.remote-packages li > span')).toContain('overflow-wrap: anywhere')
    expect(rule('.remote-packages li > button')).toContain('overflow-wrap: anywhere')
  })

  it('styles the password field of the panel like the other inputs of the app', () => {
    const field = rule('.remote-packages-pass input')
    expect(field).toContain('min-height: 44px')
    expect(rule('.remote-packages-pass')).toContain('display: grid')
  })

  // Regression (#404, #507): "Seguir como <equipo>" and "Informe PDF" overflowed or sat on the text of the match: the buttons wrap under it and shrink.
  it('lets the buttons of a row shrink and wrap a long team name inside the card', () => {
    const sides = rule('.round-sides')
    expect(sides).toContain('min-width: 0')
    expect(sides).toContain('flex-wrap: wrap')
    const button = rule('.round-sides button')
    expect(button).toContain('min-width: 0')
    expect(button).toContain('overflow-wrap: anywhere')
    expect(button).toContain('height: auto')
    expect(button).toContain('min-height: 44px')
  })

  it('the competition and the title of a match wrap instead of running in one line', () => {
    expect(rule('.match-title')).toContain('overflow-wrap: anywhere')
    expect(rule('.round-competition')).toContain('overflow-wrap: anywhere')
  })
})

// Regression (#473, feedback of 0.3.2): the filters of the matches list came out unstyled (the text box and the checkbox with the browser's
// default look, hard to hit on a phone) and the team names ran into the stars on one line.
describe('styles of the filters and of the teams of the matches list (issue #473)', () => {
  it('the filter fields are as tall and as rounded as the other inputs of the app', () => {
    const field = rule(".round-filters input:not([type='checkbox'])")
    expect(field).toContain('min-height: 44px')
    expect(field).toContain('border-radius: 10px')
    expect(field).toContain('border: 1px solid var(--line)')
    expect(rule('.select-box')).toContain('width: 100%')                       // the dropdowns of the app (#571) fill the cell like any other field
  })

  it('the filter labels look like the labels of the other fields: small, muted, over their control', () => {
    const label = rule('.select-field')
    expect(label).toContain('display: grid')
    expect(label).toContain('color: var(--muted)')
  })

  it('each team has its own line with its star, so a name never runs into the star of the other team', () => {
    expect(rule('.round-team')).toContain('display: flex')
    expect(rule('.round-team')).toContain('align-items: center')
    expect(rule('.round-info')).toContain('display: grid')
    expect(rule('.round-team .team-name')).toContain('min-width: 0')
  })
})
