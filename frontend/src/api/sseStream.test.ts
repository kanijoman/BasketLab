import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { streamResult } from './sseStream'

// Issue #452: the lineups and the rotations streams opened and read the same EventSource by hand.
class FakeEventSource {
  static last: FakeEventSource
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  constructor(public url: string) { FakeEventSource.last = this }
  close() { this.closed = true }
  send(payload: unknown) { this.onmessage?.({ data: typeof payload === 'string' ? payload : JSON.stringify(payload) }) }
}
const real = (globalThis as { EventSource?: unknown }).EventSource
beforeEach(() => { ;(globalThis as { EventSource?: unknown }).EventSource = FakeEventSource })
afterEach(() => { ;(globalThis as { EventSource?: unknown }).EventSource = real })

describe('streamResult', () => {
  it('reports the progress, then resolves with the result of the closing frame and closes the stream', async () => {
    const seen: number[][] = []
    const p = streamResult<string[]>('/x/stream', (pct, cur, tot) => seen.push([pct, cur, tot]))
    FakeEventSource.last.send({ progress: 50, current: 1, total: 2 })
    FakeEventSource.last.send({ done: true, result: ['a'] })
    await expect(p).resolves.toEqual(['a'])
    expect(seen).toEqual([[50, 1, 2]])
    expect(FakeEventSource.last.closed).toBe(true)
    expect(FakeEventSource.last.url).toBe('/x/stream')
  })

  it('rejects with the error of the closing frame', async () => {
    const p = streamResult('/x/stream')
    FakeEventSource.last.send({ done: true, error: 'sin datos' })
    await expect(p).rejects.toThrow('sin datos')
    expect(FakeEventSource.last.closed).toBe(true)
  })

  it('ignores a malformed frame and rejects when the connection fails', async () => {
    const p = streamResult('/x/stream')
    FakeEventSource.last.send('not json')
    FakeEventSource.last.onerror?.()
    await expect(p).rejects.toThrow('SSE connection error')
    expect(FakeEventSource.last.closed).toBe(true)
  })
})
