// @vitest-environment node
// The live feed client against a fake FEB that serves the REAL recording of Zamora - Leon with its real quirks
// (a 404 in the middle of the match, a late final status), feeding the REAL engine in Pyodide: the whole path of
// the live mode (issue #217) except the radio.
import fs from 'node:fs'
import path from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { loadPyodide } from 'pyodide'
import { LiveBridge, type EngineBundle } from '../engine/bridge'
import type { Alert } from '../engine/types'
import { FakeFeb, type Pack } from './fakeFeb'
import { FebClient } from './febClient'
import { LiveFeed, type FeedState } from './liveFeed'

const appRoot = path.resolve(import.meta.dirname, '../..')
const bundle: EngineBundle = JSON.parse(fs.readFileSync(path.join(appRoot, 'public/engine/live_core.json'), 'utf8'))
const realPackage = fs.readFileSync(path.join(appRoot, 'public/demo/2524470.package.json'), 'utf8')
const pack: Pack = JSON.parse(fs.readFileSync(path.join(appRoot, 'public/demo/2524470.recording.json'), 'utf8'))

let bridge: LiveBridge
beforeAll(async () => {
  bridge = new LiveBridge(await loadPyodide(), bundle)
}, 120_000)

async function playTheMatch(options: { expireTokenAt?: number } = {}) {
  const feb = new FakeFeb(pack)
  feb.at = -400  // the app connects a few minutes before kick-off
  bridge.start(realPackage)
  const states: FeedState[] = []
  const alerts: Alert[] = []
  let last: ReturnType<LiveBridge['update']> | null = null
  let expired = false
  const feed = new LiveFeed({
    client: new FebClient(feb.get), code: '2524470',
    sleep: async ms => {
      feb.at += ms / 1000  // the fake clock moves with the waiting time
      if (options.expireTokenAt !== undefined && !expired && feb.at >= options.expireTokenAt) { feb.expire(); expired = true }
    },
    now: () => feb.at * 1000,
    onState: s => states.push(s),
    onDocument: json => { last = bridge.update(json); alerts.push(...last.alerts) },
  })
  await feed.start()
  return { feb, states, alerts, last: last!, kinds: new Set(states.map(s => s.kind)) }
}

describe('live feed on the real recording', () => {
  it('follows the whole match: waits for it, rides the real 404, ends with the official score', async () => {
    const { states, alerts, last, kinds, feb } = await playTheMatch()
    expect(states[0].kind).toBe('connecting')
    expect(kinds).toEqual(new Set(['connecting', 'waiting', 'live', 'gap', 'finished']))
    expect(states[states.length - 1].kind).toBe('finished')
    expect(last.snapshot.score).toEqual({ '1008631': 38, '1008898': 59 })  // corrections of the real feed applied
    expect(alerts.length).toBeGreaterThanOrEqual(10)
    // #234: the app drops keys it has already shown, so a re-armed alert must arrive with a new key
    expect(new Set(alerts.map(a => a.key)).size).toBe(alerts.length)
    expect(last.analysis.pace?.reliable).toBe(true)
    expect(feb.at).toBeGreaterThan(7100)
  }, 180_000)

  it('the gap of the middle of the match did not break the engine: the clock only moves forward', async () => {
    const elapsed: number[] = []
    const feb = new FakeFeb(pack)
    feb.at = 5900
    bridge.start(realPackage)
    const feed = new LiveFeed({
      client: new FebClient(feb.get), code: '2524470', tailPolls: 0,
      sleep: async ms => { feb.at += ms / 1000 }, now: () => feb.at * 1000, onState: () => undefined,
      onDocument: json => { elapsed.push(bridge.update(json).snapshot.elapsed) },
    })
    await feed.start()
    expect(elapsed).toEqual([...elapsed].sort((a, b) => a - b))
    expect(elapsed.length).toBeGreaterThan(50)
  }, 120_000)

  it('renews the token when FEB expires it in the middle of the match and keeps going', async () => {
    const { feb, last } = await playTheMatch({ expireTokenAt: 3000 })
    const tokens = new Set(feb.requests.map(r => r.token).filter(Boolean))
    expect(tokens.size).toBe(2)  // the first token and its replacement
    expect(last.snapshot.score).toEqual({ '1008631': 38, '1008898': 59 })
  }, 180_000)
})
