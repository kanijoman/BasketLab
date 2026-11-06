// @vitest-environment node
// Issue #776: the engine bundle (`public/engine/live_core.json`) is GENERATED from `src/live_core` by `npm run sync-engine` and git-ignored. Running `npx vitest` directly used a
// bundle from days before and the reference-vector test failed with alerts «missing» that looked like a bug of the engine. A stale bundle is now said as what it is.
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const appRoot = path.resolve(import.meta.dirname, '../..')
const liveCore = path.resolve(appRoot, '../../src/live_core')

describe('the generated engine bundle', () => {
  it('is the current src/live_core: when it is not, the failure says to run `npm run sync-engine` (or `npm run test:run`, which does it)', () => {
    const bundle: { files: Record<string, string> } = JSON.parse(fs.readFileSync(path.join(appRoot, 'public/engine/live_core.json'), 'utf8'))
    const sources = fs.readdirSync(liveCore).filter(f => f.endsWith('.py')).sort()
    const stale = sources.filter(name => bundle.files[name] !== fs.readFileSync(path.join(liveCore, name), 'utf8'))
    const extra = Object.keys(bundle.files).filter(name => !sources.includes(name))
    expect(
      [...stale, ...extra],
      `El motor empaquetado (public/engine/live_core.json) no es el de src/live_core: ejecuta «npm run sync-engine» (o usa «npm run test:run», que lo hace antes). Distintos: ${[...stale, ...extra].join(', ')}`,
    ).toEqual([])
  })
})
