import { describe, expect, it, vi } from 'vitest'
import { FbcylFeed, type FbcylFeedOptions } from './fbcylFeed'
import type { CalendarRow, FbcylClient } from './fbcylClient'
import type { FeedState } from './feedLoop'

// Issue #446 (PR 3): the live feed of a FBCYL match. The match is in the calendar of its group from the start but only has an `adGameId` (the key of the live feed) when it is about to start,
// the stream is asked every 10 s, and once the calendar says it is played the definitive moves and stats of msstats close it. The loop (states, waits, stop) is the one of FEB's feed.

const MATCH = '149388'
const GROUP = '7298'
const row = (over: Partial<CalendarRow> = {}): CalendarRow => ({ idMatch: MATCH, round: '3', state: '0', isLive: false, adGameId: null, universallyid: null, matchStartedHour: null, ...over })

/** A scripted client: the calendar answers one row per call (the last one repeats), the stream and the msstats what the test gives. */
function client(script: { calendar: (CalendarRow | Error)[]; stream?: (string | number | Error)[]; final?: ({ moves: string; stats: string } | null)[] }) {
  const next = <T,>(list: T[] | undefined, calls: { n: number }): T | undefined => (list ? list[Math.min(calls.n++, list.length - 1)] : undefined)
  const calls = { calendar: { n: 0 }, stream: { n: 0 }, final: { n: 0 } }
  const fake = {
    calendar: vi.fn(async () => {
      const r = next(script.calendar, calls.calendar)!
      if (r instanceof Error) throw r
      return [r, row({ idMatch: '1', adGameId: '9' })]
    }),
    stream: vi.fn(async () => {
      const r = next(script.stream, calls.stream)
      if (r instanceof Error) throw r
      return typeof r === 'string' ? { status: 200, text: r } : { status: typeof r === 'number' ? r : 404, text: null }
    }),
    final: vi.fn(async () => next(script.final, calls.final) ?? null),
  }
  return fake as unknown as FbcylClient & typeof fake
}

function feed(c: FbcylClient, over: Partial<FbcylFeedOptions> = {}) {
  const states: FeedState[] = []
  const streamed: string[] = []
  const finals: { moves: string; stats: string }[] = []
  let time = 0
  const f = new FbcylFeed({
    client: c, matchId: MATCH, groupId: GROUP, intervalMs: 10, waitingIntervalMs: 60, tailPolls: 0, calendarEveryMs: 100,
    sleep: async ms => { time += ms }, now: () => time,
    onState: s => states.push(s), onStream: async body => { streamed.push(body) }, onFinal: async (moves, stats) => { finals.push({ moves, stats }) },
    ...over,
  })
  return { f, states, streamed, finals }
}

describe('FbcylFeed: before the match', () => {
  it('waits while the match has no adGameId, asking the calendar and nothing else', async () => {
    const c = client({ calendar: [row(), row(), row({ adGameId: '23958', isLive: true })], stream: ['{"period":1}'] })
    const streamed: string[] = []
    const seen: FeedState[] = []
    const f = new FbcylFeed({ client: c, matchId: MATCH, groupId: GROUP, intervalMs: 10, waitingIntervalMs: 60, calendarEveryMs: 1_000_000, sleep: async () => undefined, now: () => 0,
      onState: s => { seen.push(s); if (s.kind === 'live') f.stop() }, onStream: async b => { streamed.push(b) }, onFinal: async () => undefined })
    await f.start()
    expect(seen.map(s => s.kind)).toEqual(['connecting', 'waiting', 'waiting', 'live'])
    expect(c.calendar).toHaveBeenCalledWith(GROUP)
    expect(streamed).toEqual(['{"period":1}'])
  })

  it('is not the calendar of the match: it says so and keeps asking (a gap, never «not started»)', async () => {
    const c = client({ calendar: [row({ idMatch: '5' })] })
    const seen: FeedState[] = []
    const f = new FbcylFeed({ client: c, matchId: MATCH, groupId: GROUP, sleep: async () => undefined, now: () => 0, tailPolls: 0,
      onState: s => { seen.push(s); if (s.kind === 'gap') f.stop() }, onStream: async () => undefined, onFinal: async () => undefined })
    await f.start()
    expect(seen.at(-1)).toMatchObject({ kind: 'gap', message: expect.stringMatching(/FBCYL.*calendario/i) })
  })

  it('a calendar that cannot be read is a gap with the name of the league', async () => {
    const c = client({ calendar: [new Error('timeout')] })
    const seen: FeedState[] = []
    const f = new FbcylFeed({ client: c, matchId: MATCH, groupId: GROUP, sleep: async () => undefined, now: () => 0, tailPolls: 0,
      onState: s => { seen.push(s); if (s.kind === 'gap') f.stop() }, onStream: async () => undefined, onFinal: async () => undefined })
    await f.start()
    expect(seen.at(-1)).toMatchObject({ kind: 'gap', message: expect.stringMatching(/FBCYL.*timeout/i) })
  })
})

describe('FbcylFeed: during the match', () => {
  it('hands every reading of the stream to the engine and reads the calendar only now and then', async () => {
    const c = client({ calendar: [row({ adGameId: '23958', isLive: true })], stream: ['{"n":1}', '{"n":2}', '{"n":3}', '{"n":4}'] })
    const streamed: string[] = []
    let time = 0
    const f = new FbcylFeed({ client: c, matchId: MATCH, groupId: GROUP, intervalMs: 10, tailPolls: 0, calendarEveryMs: 25, sleep: async ms => { time += ms }, now: () => time,
      onState: () => { if (streamed.length >= 4) f.stop() }, onStream: async b => { streamed.push(b) }, onFinal: async () => undefined })
    await f.start()
    expect(streamed).toEqual(['{"n":1}', '{"n":2}', '{"n":3}', '{"n":4}'])
    expect(c.stream).toHaveBeenCalledWith('23958')
    expect(c.calendar.mock.calls.length).toBeLessThan(c.stream.mock.calls.length)         // the calendar is big: not read every 10 s
  })

  it('an answer that is not good in the middle of the match is a gap and the last state stays (the stream is asked again)', async () => {
    const c = client({ calendar: [row({ adGameId: '23958', isLive: true })], stream: ['{"n":1}', 503, '{"n":3}'] })
    const kinds: string[] = []
    const failures: string[] = []
    const f = new FbcylFeed({ client: c, matchId: MATCH, groupId: GROUP, intervalMs: 10, tailPolls: 0, calendarEveryMs: 1_000_000, sleep: async () => undefined, now: () => 0,
      onState: s => { kinds.push(s.kind); if (kinds.filter(k => k === 'live').length === 2) f.stop() }, onStream: async () => undefined, onFinal: async () => undefined, onFailure: e => failures.push(e) })
    await f.start()
    expect(kinds).toEqual(['connecting', 'live', 'gap', 'live'])
    expect(failures).toEqual(['stream'])
  })
})

describe('FbcylFeed: the end', () => {
  it('when the calendar says the match is played it closes it with the moves and the stats of msstats and finishes', async () => {
    const played = row({ adGameId: '23958', state: '1', universallyid: 'abc123' })
    const c = client({ calendar: [played], stream: ['{"n":1}'], final: [{ moves: '[1]', stats: '{"s":1}' }] })
    const { f, states, finals } = feed(c)
    await f.start()
    expect(c.final).toHaveBeenCalledWith('abc123')
    expect(finals).toEqual([{ moves: '[1]', stats: '{"s":1}' }])
    expect(states.at(-1)).toEqual({ kind: 'finished' })
  })

  it('without the msstats yet (it is published a little after) it keeps following the stream and tries again at the next calendar reading', async () => {
    const played = row({ adGameId: '23958', state: '1', universallyid: 'abc123' })
    const c = client({ calendar: [played], stream: ['{"n":1}'], final: [null, null, { moves: '[2]', stats: '{"s":2}' }] })
    const { f, states, streamed, finals } = feed(c, { calendarEveryMs: 0 })
    await f.start()
    expect(finals).toEqual([{ moves: '[2]', stats: '{"s":2}' }])
    expect(streamed.length).toBeGreaterThanOrEqual(2)
    expect(states.at(-1)).toEqual({ kind: 'finished' })
  })

  it('a match that was already played when the app connects is closed at once, with no stream', async () => {
    const played = row({ adGameId: '23958', state: '1', universallyid: 'abc123' })
    const c = client({ calendar: [played], stream: [404], final: [{ moves: '[1]', stats: '{}' }] })
    const { f, finals } = feed(c)
    await f.start()
    expect(finals).toHaveLength(1)
  })

  it('after stop() it reports and hands over nothing', async () => {
    const c = client({ calendar: [row({ adGameId: '23958', isLive: true })], stream: ['{"n":1}'] })
    const { f, states, streamed } = feed(c)
    f.stop()
    await f.start()
    expect(states).toEqual([])
    expect(streamed).toEqual([])
  })

  it('once closed it asks nothing more, whatever the tail of the loop of the other league is', async () => {
    const played = row({ adGameId: '23958', state: '1', universallyid: 'abc123' })
    const c = client({ calendar: [played], stream: ['{"n":1}'], final: [{ moves: '[1]', stats: '{}' }] })
    const { f } = feed(c, { tailPolls: 5 })
    await f.start()
    expect(c.final).toHaveBeenCalledTimes(1)
    expect(c.calendar).toHaveBeenCalledTimes(1)
  })
})
