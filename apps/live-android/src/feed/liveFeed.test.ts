import { describe, expect, it, vi } from 'vitest'
import type { FebClient, FebResult } from './febClient'
import { LiveFeed, type FeedState } from './liveFeed'

type Script = Record<'boxscore' | 'keyfacts' | 'shotchart', (FebResult | Error)[]>

const ok = (json: unknown): FebResult => ({ status: 200, json })
const notFound: FebResult = { status: 404, json: null }
const box = (status: string) => ok({ HEADER: { status, time: '10:00' }, BOXSCORE: { TEAM: [] } })
const kf = (n: number) => ok({ PLAYBYPLAY: { LINES: Array.from({ length: n }, (_, i) => ({ num: String(i + 1) })) } })
const sc = ok({ SHOTCHART: { SHOTS: [] } })

/** One scripted answer per poll and endpoint; the last one repeats. */
function setup(script: Partial<Script>, opts: { tailPolls?: number } = {}) {
  const full: Script = { boxscore: [notFound], keyfacts: [kf(0)], shotchart: [sc], ...script }
  const used = { boxscore: 0, keyfacts: 0, shotchart: 0 }
  const client = {
    fetch: vi.fn(async (_code: string, endpoint: keyof Script) => {
      const queue = full[endpoint]
      const item = queue[Math.min(used[endpoint]++, queue.length - 1)]
      if (item instanceof Error) throw item
      return item
    }),
  } as unknown as FebClient
  const documents: { doc: Record<string, unknown> }[] = []
  const states: FeedState[] = []
  const sleeps: number[] = []
  let clock = 1_000_000
  const feed = new LiveFeed({
    client, code: '777', tailPolls: opts.tailPolls ?? 2,
    onDocument: json => { documents.push({ doc: JSON.parse(json) }) },
    onState: s => states.push(s),
    sleep: async ms => { sleeps.push(ms); clock += ms },
    now: () => clock,
  })
  return { feed, client, documents, states, sleeps, kinds: () => states.map(s => s.kind) }
}

describe('LiveFeed', () => {
  it('waits while FEB answers 404 before the match, polling slowly, and then goes live', async () => {
    const t = setup({ boxscore: [notFound, notFound, box('1'), box('2'), box('3')] }, { tailPolls: 0 })
    await t.feed.start()
    expect(t.kinds().slice(0, 3)).toEqual(['connecting', 'waiting', 'waiting'])
    expect(t.sleeps.slice(0, 2)).toEqual([60_000, 60_000])  // not started: one poll a minute
    expect(t.states.some(s => s.kind === 'live')).toBe(true)
    expect(t.documents).toHaveLength(3)
  })

  it('merges the three endpoints into the document the engine expects', async () => {
    const t = setup({ boxscore: [box('2'), box('3')], keyfacts: [kf(7)] })
    await t.feed.start()
    const doc = t.documents[0].doc as { HEADER: { status: string }; PLAYBYPLAY: { LINES: unknown[] }; SHOTCHART: { SHOTS: unknown[] } }
    expect(doc.HEADER.status).toBe('2')
    expect(doc.PLAYBYPLAY.LINES).toHaveLength(7)
    expect(doc.SHOTCHART.SHOTS).toEqual([])
  })

  it('polls every 10 seconds while the match is on', async () => {
    const t = setup({ boxscore: [box('2'), box('2'), box('2'), box('3')] }, { tailPolls: 0 })
    await t.feed.start()
    expect(t.sleeps).toEqual([10_000, 10_000, 10_000])
  })

  it('a 404 in the middle of the match keeps the last state: no update, a "gap" notice, and it resumes (real quirk)', async () => {
    const t = setup({ boxscore: [box('2'), notFound, notFound, box('2'), box('3')], keyfacts: [kf(5), kf(5), kf(5), kf(6)] }, { tailPolls: 0 })
    await t.feed.start()
    expect(t.kinds()).toContain('gap')
    expect(t.states.find(s => s.kind === 'gap')).toMatchObject({ lastOkAt: expect.any(Number) })
    expect(t.documents).toHaveLength(3)  // two 404 polls produced no document
    expect(t.kinds().slice(-1)[0]).toBe('finished')
    expect(t.sleeps.every(ms => ms === 10_000)).toBe(true)  // once the match is on a gap does not slow the polling down
  })

  it('a 404 of only one endpoint also skips the update (an incomplete document would mislead the engine)', async () => {
    const t = setup({ boxscore: [box('2'), box('2'), box('3')], keyfacts: [kf(5), notFound, kf(6)] }, { tailPolls: 0 })
    await t.feed.start()
    expect(t.documents).toHaveLength(2)
    expect(t.kinds()).toContain('gap')
  })

  it('a network error is a gap, never a crash, and the loop keeps trying', async () => {
    const t = setup({ boxscore: [box('2'), new TypeError('Failed to fetch'), box('3')] }, { tailPolls: 0 })
    await t.feed.start()
    expect(t.kinds()).toContain('gap')
    expect(t.documents).toHaveLength(2)
  })

  it('does not treat a 404 after the match was on as "not started" nor as the end', async () => {
    const t = setup({ boxscore: [box('2'), notFound, notFound, notFound, box('3')] }, { tailPolls: 0 })
    await t.feed.start()
    expect(t.kinds()).not.toContain('waiting')
    expect(t.kinds().filter(k => k === 'finished')).toHaveLength(1)
  })

  it('keeps polling a few more times after the final status and then stops (late final status, real quirk)', async () => {
    const t = setup({ boxscore: [box('2'), box('3')] }, { tailPolls: 2 })
    await t.feed.start()
    const finals = t.documents.filter(d => (d.doc.HEADER as { status: string }).status === '3')
    expect(finals).toHaveLength(3)  // the first final document plus two tail polls
    expect(t.kinds().slice(-1)[0]).toBe('finished')
  })

  it('the engine failing on a document is reported and does not stop the feed', async () => {
    const t = setup({ boxscore: [box('2'), box('2'), box('3')] }, { tailPolls: 0 })
    let calls = 0
    const failing = new LiveFeed({
      client: (t.client as unknown) as FebClient, code: '777', tailPolls: 0,
      onDocument: () => { if (calls++ === 0) throw new Error('boom') },
      onState: s => t.states.push(s), sleep: async () => undefined, now: () => 0,
    })
    await failing.start()
    expect(calls).toBe(3)
    expect(t.states.some(s => s.kind === 'gap' && /boom/.test(s.message ?? ''))).toBe(true)
  })

  it('stop() ends the loop at once', async () => {
    const t = setup({ boxscore: [box('2')] })
    let n = 0
    const feed = new LiveFeed({
      client: t.client, code: '777', onDocument: () => { n++ }, onState: () => undefined,
      sleep: async () => { if (n >= 2) feed.stop() }, now: () => 0,
    })
    await feed.start()
    expect(n).toBe(2)
  })

  it('after stop() nothing more is reported — no state, no document — not even from a round that was in flight (CI flake)', async () => {
    // CI of #218 failed with "window is not defined": the loop of a finished test woke up from its sleep and
    // called a React setState after the test environment was gone.
    const states: FeedState[] = []
    const documents: string[] = []
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    const client = {
      fetch: vi.fn(async (_code: string, endpoint: string) => {
        if (endpoint === 'boxscore') await gate  // the first round is still waiting for FEB when stop() arrives
        return endpoint === 'boxscore' ? box('2') : endpoint === 'keyfacts' ? kf(1) : sc
      }),
    } as unknown as FebClient
    const feed = new LiveFeed({
      client, code: '777', onDocument: json => { documents.push(json) }, onState: s => states.push(s),
      sleep: async () => undefined, now: () => 0,
    })
    const running = feed.start()
    feed.stop()
    release()
    await running
    expect(documents).toEqual([])
    expect(states.map(s => s.kind)).toEqual(['connecting'])  // nothing after the stop, not even "stopped"
  })
})
