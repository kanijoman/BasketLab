// @vitest-environment node
// The real shipped engine (generated bundle) running inside real Pyodide, compared with the
// shared reference vectors: if this passes, the tablet computes what CPython computes.
import fs from 'node:fs'
import path from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { loadPyodide } from 'pyodide'
import zlib from 'node:zlib'
import { LiveBridge, type EngineBundle } from './bridge'
import type { EngineOutput } from './types'

const appRoot = path.resolve(import.meta.dirname, '../..')
const repoRoot = path.resolve(appRoot, '../..')
const bundle: EngineBundle = JSON.parse(fs.readFileSync(path.join(appRoot, 'public/engine/live_core.json'), 'utf8'))
const demoPackage = fs.readFileSync(path.join(appRoot, 'public/demo/package.json'), 'utf8')
const demoGame = fs.readFileSync(path.join(appRoot, 'public/demo/game.json'), 'utf8')
const realPackage = fs.readFileSync(path.join(appRoot, 'public/demo/2524470.package.json'), 'utf8')
const recording = fs.readFileSync(path.join(appRoot, 'public/demo/2524470.recording.json'), 'utf8')
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
    expect(bridge.loadReplay(demoGame).duration).toBe(2400)   // four periods: the sample has no overtime (its closing line at 40:00 once counted as one, #561)
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

  it('builds the post-match report of the finished game inside Pyodide (issue #409)', () => {
    const meta = bridge.start(demoPackage)
    const alerts = [{ alert: { key: 'k', id: 'fatigue_high', severity: 'info', category: 'rotacion', message: 'm', evidence: {}, proposal: [], rearm_s: null }, at: 'Q2 03:00' }]
    const report = bridge.report(demoGame, alerts as never, meta.team.id)
    expect(report.match.own.name.trim()).toBe('ACEITES ABRIL ADBA SANFER')
    expect(report.match.periods.length).toBeGreaterThanOrEqual(4)
    expect(['win', 'loss']).toContain(report.match.result)
    expect(report.match.periods.reduce((n, p) => n + p.own, 0)).toBe(report.match.score.own)
    expect(report.alerts[0]).toMatchObject({ key: 'k', period: 2, clock: '03:00' })
    // the own team is given, so the other side of the same game can be reported without restarting the session
    const rival = bridge.report(demoGame, [], meta.rival.id)
    expect(rival.match.own.id).toBe(meta.rival.id)
    expect(rival.match.score.own).toBe(report.match.score.rival)
  }, 60_000)

  it('records the feed it is given a time for and returns it in the recording format, inside Pyodide (issue #416)', () => {
    bridge.start(realPackage)
    bridge.beginRecording('2524470', '2026-10-10T14:55:03+00:00')
    expect(bridge.recording()).toBeNull()
    const doc = JSON.parse(demoGame)
    bridge.update(JSON.stringify(doc), 0)
    bridge.recordGap('boxscore', 5)
    bridge.update(JSON.stringify(doc), 12)
    const packed = bridge.recording() as { v: number; match: string; frames: { t: number }[]; gaps: Record<string, number[][]> }
    expect(packed.v).toBe(1)
    expect(packed.match).toBe('2524470')
    expect(packed.frames.map(f => f.t)).toEqual([0, 12])
    expect(packed.gaps).toEqual({ boxscore: [[5, 12]] })
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

describe('alert modes on Pyodide (issue #130)', () => {
  function alertsIn(mode: string | null): number {
    bridge.setMode(mode)
    bridge.start(realPackage)
    bridge.loadRecording(recording)
    let total = 0
    for (let s = 0; s <= 7200; s += 60) total += bridge.playRecording(s).output?.alerts.length ?? 0
    return total
  }

  it('the mode chosen before the session starts applies to it, and it can change while the session runs', () => {
    const aggressive = alertsIn('aggressive')
    const conservative = alertsIn('conservative')
    expect(aggressive).toBeGreaterThan(conservative)
    expect(alertsIn(null)).toBeGreaterThan(conservative)                  // no mode: the medium one
    bridge.setMode('conservative')                                         // with a session running: no error
    expect(() => bridge.playRecording(3000)).not.toThrow()
  }, 300_000)
})

describe('real recorded match on Pyodide (issue #174)', () => {
  it('plays the recording through the engine: not there yet, a moment, a real 404, the end', () => {
    bridge.start(realPackage)
    const info = bridge.loadRecording(recording)
    expect(info.match).toBe('2524470')
    expect(info.duration).toBeGreaterThan(7100)

    expect(bridge.playRecording(-5)).toEqual({ feed: 'waiting', output: null })
    const mid = bridge.playRecording(3000)
    expect(mid.feed).toBe('ok')
    expect(mid.output!.snapshot.elapsed).toBeGreaterThan(1000)
    expect(bridge.playRecording(6000)).toEqual({ feed: 'gap', output: null }) // FEB answered 404 here in the real match

    let last = mid.output
    for (let s = 3060; s <= info.duration + 60; s += 60) last = bridge.playRecording(s).output ?? last
    expect(last!.snapshot.score).toEqual({ '1008631': 38, '1008898': 59 }) // the official result, corrections included
    expect(last!.analysis.pace?.reliable).toBe(true)
  }, 120_000)
})
})


// Issue #446 (PR 3): a FBCYL match followed from the streaming service. The REAL end of Salamanca–UNILEON (7/11/2026): the service answers readings that go backwards mixed with the right
// ones; the real engine inside Pyodide ignores them and closes with the moves of msstats.
describe('LiveBridge on a FBCYL match (issue #446)', () => {
  const fixture = (name: string) => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(repoRoot, 'tests/fixtures', name))).toString('utf8'))
  const ending: { body: Record<string, unknown> }[] = fixture('fbcyl_streaming_end_20261107.json.gz').readings
  const full = fixture('fbcyl_streaming_20261107.json.gz')
  const HOME = '39731'
  const AWAY = '39609'

  it('ignores the readings that go backwards and shows the 4th period at 81-75 at the end', () => {
    bridge.start(realPackage)
    const outputs = ending.map((r, i) => bridge.updateStreaming(JSON.stringify(r.body), i * 10))
    expect(outputs.map(o => 'stale' in o)).toEqual([false, true, false, true, false, true, true])
    const shown = outputs.filter((o): o is EngineOutput => !('stale' in o))
    expect(shown.map(o => [o.snapshot.period, o.snapshot.score[HOME], o.snapshot.score[AWAY]])).toEqual([[4, 77, 75], [4, 81, 75], [4, 81, 75]])
  })

  it('keeps the FEB document of the last reading to review the match later, and has none before the first', () => {
    bridge.start(realPackage)
    expect(bridge.lastDocument()).toBeNull()
    bridge.updateStreaming(JSON.stringify(ending[2].body), 0)
    const doc = JSON.parse(bridge.lastDocument()!)
    expect([doc.HEADER.source, doc.HEADER.status, doc.PLAYBYPLAY.LINES.length > 500]).toEqual(['fbcyl', '2', true])
    bridge.updateStreaming(JSON.stringify(ending[3].body), 10)                                          // stale: the document is still the 609 one
    expect(JSON.parse(bridge.lastDocument()!).PLAYBYPLAY.LINES.length).toBe(doc.PLAYBYPLAY.LINES.length)
  })

  it('closes the match with the definitive moves and stats of msstats', () => {
    bridge.start(realPackage)
    for (const r of ending) bridge.updateStreaming(JSON.stringify(r.body))
    const final = bridge.updateFbcylFinal(JSON.stringify(full.msstats_moves), JSON.stringify(full.msstats_stats), 60)
    expect([final.snapshot.period, final.snapshot.score[HOME], final.snapshot.score[AWAY]]).toEqual([4, 81, 75])
    expect(bridge.updateStreaming(JSON.stringify(ending[2].body))).toEqual({ stale: true })           // nothing of the stream is followed after the closing
  })
})
