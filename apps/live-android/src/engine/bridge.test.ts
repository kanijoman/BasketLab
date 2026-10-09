// @vitest-environment node
// The real shipped engine (generated bundle) running inside real Pyodide, compared with the
// shared reference vectors: if this passes, the tablet computes what CPython computes.
import fs from 'node:fs'
import path from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { loadPyodide } from 'pyodide'
import { LiveBridge, type EngineBundle } from './bridge'

const appRoot = path.resolve(import.meta.dirname, '../..')
const repoRoot = path.resolve(appRoot, '../..')
const bundle: EngineBundle = JSON.parse(fs.readFileSync(path.join(appRoot, 'public/engine/live_core.json'), 'utf8'))
const demoPackage = fs.readFileSync(path.join(appRoot, 'public/demo/package.json'), 'utf8')
const demoGame = fs.readFileSync(path.join(appRoot, 'public/demo/game.json'), 'utf8')
const vectors = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8'))
const expected: { elapsed: number; score: Record<string, number>; alerts: string[] }[] = vectors.expected.engine.checkpoints

let bridge: LiveBridge

beforeAll(async () => {
  bridge = new LiveBridge(await loadPyodide(), bundle)
}, 120_000)

describe('LiveBridge on Pyodide', () => {
  it('bundles every live_core module and nothing else', () => {
    expect(Object.keys(bundle.files)).toEqual(expect.arrayContaining(['session.py', 'engine.py', 'advice.py', 'zones.py']))
    expect(Object.keys(bundle.files).every(f => f.endsWith('.py'))).toBe(true)
  })

  it('starts a session from the demo package', () => {
    const meta = bridge.start(demoPackage)
    expect(meta.team.name).toBe('ACEITES ABRIL ADBA SANFER')
    expect(meta.rival.name).toBe('MANRESA CBF A')
  })

  it('loads the demo game and reports its duration', () => {
    expect(bridge.loadReplay(demoGame).duration).toBe(2700)
  })

  it('reproduces the reference vectors (score, clock and new alerts per checkpoint)', () => {
    bridge.start(demoPackage)
    bridge.loadReplay(demoGame)
    for (const exp of expected) {
      const out = bridge.replay(exp.elapsed)
      expect(out.snapshot.elapsed).toBe(exp.elapsed)
      expect(out.snapshot.score).toEqual(exp.score)
      expect(out.alerts.map(a => a.key)).toEqual(exp.alerts)
    }
  }, 60_000)

  it('rejects a corrupted package with a readable error', () => {
    const broken = JSON.parse(demoPackage)
    broken.package.team.name = 'otro'
    expect(() => bridge.start(JSON.stringify(broken))).toThrow(/checksum/i)
  })

  it('keeps a full-game update well under a second (fluidity)', () => {
    bridge.start(demoPackage)
    bridge.loadReplay(demoGame)
    const t0 = performance.now()
    bridge.replay(1800)
    expect(performance.now() - t0).toBeLessThan(1000)
  })
})
