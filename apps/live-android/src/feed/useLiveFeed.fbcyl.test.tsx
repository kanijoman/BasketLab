import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { EngineApi } from '../engine/client'
import type { EngineOutput, StreamingOutput } from '../engine/types'
import type { Device } from './device'
import { calendarUrl, movesUrl, statsUrl, streamUrl } from './fbcylClient'
import type { HttpGet } from './febClient'
import { useLiveFeed } from './useLiveFeed'

// Issue #446 (PR 3): the live hook follows a FBCYL match with the REAL end of Salamanca–UNILEON (7/11/2026): readings that go backwards are not shown, the match is closed with the moves and
// stats of msstats, kept for review and recorded. The engine is a double that answers like the real one (the real one is tested in CPython and Pyodide); the services are a fake HTTP.
const fixtures = path.resolve(import.meta.dirname, '../../../../tests/fixtures')
const load = (name: string) => JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(fixtures, name))).toString('utf8'))
const ending: { body: { period: number; moves: unknown[] } }[] = load('fbcyl_streaming_end_20261107.json.gz').readings
const full = load('fbcyl_streaming_20261107.json.gz')
const calendarRows: Record<string, unknown>[] = load('fbcyl_calendar_7298.json.gz').rows

const MATCH = '149388'
const GROUP = '7298'
const AD_GAME = '23958'
const UUID = 'abc123'

/** The calendar of the group with the match of the test as the test says: its state and its keys. */
const encoded = new Map<string, string>()                         // the calendar is big: each version is encoded once, not at every round of the feed
function calendar(over: Record<string, unknown>): string {
  const key = JSON.stringify(over)
  const known = encoded.get(key)
  if (known !== undefined) return known
  const rounds: Record<string, { date: unknown; matches: Record<string, unknown> }> = {}
  for (const r of calendarRows) (rounds[String(r.round)] ??= { date: r.round_date, matches: {} }).matches[String(r.idMatch)] = String(r.idMatch) === MATCH ? { ...r, ...over } : r
  const text = Buffer.from(JSON.stringify({ result: 'OK', messageData: { rounds } }), 'utf8').toString('base64')
  encoded.set(key, text)
  return text
}

const OUT = { snapshot: { period: 4 }, alerts: [], analysis: {} } as unknown as EngineOutput
const IDLE_DEVICE: Device = { keepAwake: async () => true, allowSleep: async () => undefined, onResume: () => () => undefined }

/** An engine that answers like the real one for the stream: a reading with less than the best seen is stale. */
function engine() {
  let best: [number, number] = [0, 0]
  const e = {
    updateStreaming: vi.fn(async (body: string): Promise<StreamingOutput> => {
      const b = JSON.parse(body) as { period: number; moves: unknown[] }
      const mark: [number, number] = [b.period, b.moves.length]
      if (mark[0] < best[0] || (mark[0] === best[0] && mark[1] < best[1])) return { stale: true }
      best = mark
      return OUT
    }),
    updateFbcylFinal: vi.fn(async () => OUT),
    lastDocument: vi.fn(async () => '{"FEB":"document"}'),
    beginRecording: vi.fn(async () => undefined),
    recordGap: vi.fn(async () => undefined),
    recording: vi.fn(async () => ({ frames: 1 })),
  }
  return e as unknown as EngineApi & typeof e
}

/** The fake services: the stream answers the readings in order (the last one repeats); after `playedAfter` of them the calendar says the match is played. */
function services(playedAfter: number, over: { msstats?: boolean } = {}) {
  let streamed = 0
  const http: HttpGet = vi.fn(async url => {
    if (url === calendarUrl(GROUP)) {
      return { status: 200, text: calendar(streamed >= playedAfter ? { adGameId: AD_GAME, state: '1', universallyid: UUID } : { adGameId: AD_GAME, state: '0', isLive: true }) }
    }
    if (url === streamUrl(AD_GAME)) return { status: 200, text: JSON.stringify(ending[Math.min(streamed++, ending.length - 1)].body) }
    if (url === movesUrl(UUID)) return over.msstats === false ? { status: 404, text: '' } : { status: 200, text: JSON.stringify(full.msstats_moves) }
    if (url === statsUrl(UUID)) return { status: 200, text: JSON.stringify(full.msstats_stats) }
    return { status: 404, text: '' }
  })
  return http
}

const TIMING = { intervalMs: 1, waitingIntervalMs: 1, calendarEveryMs: 0, sleep: (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms)), now: () => 1_000 }   // a real pause: a loop that never yields starves everything else

function hook(eng: EngineApi, http: HttpGet, extra: { onFinished?: (doc: string, code: string, complete: boolean) => void; onRecording?: (r: { code: string; recording: unknown; complete: boolean }) => void; onNote?: (text: string) => void; device?: Device } = {}) {
  const onOutput = vi.fn()
  const { result } = renderHook(() => useLiveFeed({ engine: eng, http, device: extra.device ?? IDLE_DEVICE, timing: TIMING, onOutput, restart: async () => undefined,
    onFinished: extra.onFinished, onRecording: extra.onRecording, onNote: extra.onNote }))
  return { result, onOutput }
}

describe('useLiveFeed with a FBCYL match', () => {
  it('follows the stream, does not show the readings that go backwards, closes with msstats, keeps the match and the recording', async () => {
    const eng = engine()
    const onFinished = vi.fn()
    const onRecording = vi.fn()
    const { result, onOutput } = hook(eng, services(ending.length), { onFinished, onRecording })
    await act(async () => { await result.current.connect(`fbcyl-${MATCH}`, { fbcylGroup: GROUP }) })
    await waitFor(() => expect(result.current.state.kind).toBe('finished'), { timeout: 5_000 })
    expect(eng.updateStreaming).toHaveBeenCalledTimes(ending.length)
    expect(onOutput).toHaveBeenCalledTimes(3 + 1)                                  // 593, 609, 609 (the repeated one) and the closing; the 4 stale ones are not shown
    expect(eng.updateFbcylFinal).toHaveBeenCalledTimes(1)
    expect(JSON.parse((eng.updateFbcylFinal.mock.calls[0] as unknown as string[])[0])).toHaveLength(609)
    expect(onFinished).toHaveBeenCalledWith('{"FEB":"document"}', `fbcyl-${MATCH}`, true)
    expect(onRecording).toHaveBeenCalledWith({ code: `fbcyl-${MATCH}`, recording: { frames: 1 }, complete: true })
  })

  it('keeps asking the stream while msstats does not have the definitive data yet', async () => {
    const eng = engine()
    const http = services(2, { msstats: false })
    const { result } = hook(eng, http)
    await act(async () => { await result.current.connect(`fbcyl-${MATCH}`, { fbcylGroup: GROUP }) })
    await waitFor(() => expect((http as ReturnType<typeof vi.fn>).mock.calls.filter(c => c[0] === movesUrl(UUID)).length).toBeGreaterThan(1), { timeout: 5_000 })
    expect(result.current.state.kind).not.toBe('finished')
    expect(eng.updateFbcylFinal).not.toHaveBeenCalled()
    act(() => result.current.disconnect())
  })

  it('a package without the group of the match says so instead of looking for a match it cannot find', async () => {
    const eng = engine()
    const http = services(ending.length)
    const { result } = hook(eng, http)
    await act(async () => { await result.current.connect(`fbcyl-${MATCH}`) })
    expect(result.current.state).toMatchObject({ kind: 'gap', message: expect.stringMatching(/grupo.*FBCYL|FBCYL.*grupo/i) })
    expect(http).not.toHaveBeenCalled()
  })

  it('the notes of the session say the league of the match, not FEB', async () => {
    const eng = engine()
    let resume: ((reason: 'foreground' | 'network') => void) | null = null
    const device: Device = { keepAwake: async () => true, allowSleep: async () => undefined, onResume: cb => { resume = cb; return () => undefined } }
    const onNote = vi.fn()
    const { result } = hook(eng, services(10_000), { onNote, device })
    await act(async () => { await result.current.connect(`fbcyl-${MATCH}`, { fbcylGroup: GROUP }) })
    await waitFor(() => expect(resume).not.toBeNull())
    act(() => resume!('foreground'))
    expect(onNote).toHaveBeenCalledWith(expect.stringMatching(/FBCYL/))
    expect(onNote.mock.calls.map(c => String(c[0])).join(' ')).not.toMatch(/FEB/)
    act(() => result.current.disconnect())
  })

  it('writes no delay note to the session: FBCYL says neither the age of its cache nor when each move was logged, and a «datos de FEB» note would be false', async () => {
    const eng = engine()
    const onNote = vi.fn()
    const { result } = hook(eng, services(10_000), { onNote })
    await act(async () => { await result.current.connect(`fbcyl-${MATCH}`, { fbcylGroup: GROUP }) })
    await waitFor(() => expect(eng.updateStreaming.mock.calls.length).toBeGreaterThan(3), { timeout: 5_000 })
    act(() => result.current.disconnect())
    expect(onNote.mock.calls.map(c => String(c[0])).filter(t => /retraso/i.test(t))).toEqual([])
  })

  it('a match of FEB is followed as always: the code without prefix goes to FEB', async () => {
    const eng = engine()
    const febHttp: HttpGet = vi.fn(async () => ({ status: 404, text: '' }))
    const { result } = hook(eng, febHttp)
    await act(async () => { await result.current.connect('2524475') })
    expect(((febHttp as ReturnType<typeof vi.fn>).mock.calls[0] as unknown as string[])[0]).toMatch(/baloncestoenvivo\.feb\.es\/partido\/2524475/)       // FEB's way: the page of the match first (its token)
    expect(eng.updateStreaming).not.toHaveBeenCalled()
    act(() => result.current.disconnect())
  })
})
