import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// Issue #201: client.ts was 1192 lines; it is now a barrel over one module per domain, and no module of api/ goes past the 500 lines of the work rules.
const DIR = __dirname
const lines = (file: string) => readFileSync(join(DIR, file), 'utf-8').split('\n').length
const sources = readdirSync(DIR).filter(f => f.endsWith('.ts') && !f.endsWith('.test.ts'))

describe('modules of the API client (issue #201)', () => {
  it.each(sources)('%s stays under 500 lines', file => {
    expect(lines(file)).toBeLessThanOrEqual(500)
  })

  it('client.ts is a barrel that only re-exports', () => {
    const code = readFileSync(join(DIR, 'client.ts'), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '').split('\n').map(l => l.trim()).filter(Boolean)
    expect(code.every(l => l.startsWith('export ') && l.includes(' from '))).toBe(true)
  })
})
