import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(__dirname, 'index.css'), 'utf8')

function rule(name: string): string {
  const start = css.indexOf(`.${name} {`)
  if (start < 0) throw new Error(`.${name} not found`)
  return css.slice(start, css.indexOf('}', start))
}

describe('button styles', () => {
  // Regression: a disabled "Generar paquete" looked clickable (it changed colour on hover), so it was pressed
  // expecting it to work. Disabled buttons must look disabled and must not react to the pointer.
  // The hover goes through :not(:disabled), not :enabled, so links (<a class="btn-primary">) keep their hover.
  it.each(['btn-primary', 'btn-secondary', 'btn-ghost'])('%s looks disabled and has no hover when disabled', name => {
    const r = rule(name)
    expect(r).toContain('disabled:opacity-50')
    expect(r).toContain('disabled:cursor-not-allowed')
    expect(r).toContain('[&:not(:disabled)]:hover:')
    expect(r.replaceAll('[&:not(:disabled)]:hover:', '')).not.toContain('hover:')
  })
})
