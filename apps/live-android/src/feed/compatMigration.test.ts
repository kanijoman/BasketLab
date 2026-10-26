import { describe, expect, it } from 'vitest'
import { memoryFinishedStore, type FinishedMatch } from './finishedStore'
import { memoryRecordingStore, type SavedRecording } from './recordingStore'
import { COMPAT_KEY, purgeStale } from './compatMigration'
import { REPLAY_COMPAT } from './replayCompat'

const finished = (code: string, compat?: number): FinishedMatch =>
  ({ code, title: `LEON – ${code}`, savedAt: `2026-10-2${code}T20:00:00Z`, ownId: '1', alerts: [], plaintext: '{}', game: '{}', ...(compat === undefined ? {} : { compat }) })
const recording = (code: string, compat?: number): SavedRecording =>
  ({ code, title: `GRAB – ${code}`, savedAt: `2026-10-2${code}T20:00:00Z`, complete: true, frames: 3, encoding: 'raw', bytes: new Uint8Array(), ...(compat === undefined ? {} : { compat }) })

function memory(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial))
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: k => void data.delete(k), clear: () => data.clear(), key: () => null, get length() { return data.size } }
}

// The version that raises REPLAY_COMPAT (0.4.1: a new prior and a calibration per family) cannot replay what an older one kept: the first time it runs it clears
// those matches and says so, instead of leaving a list of matches that replay wrong.
describe('purgeStale (issue #562, 0.4.1)', () => {
  it('removes the finished matches and the recordings kept under an older compatibility and says which', async () => {
    const f = memoryFinishedStore([finished('1'), finished('2', 2), finished('3', REPLAY_COMPAT)])
    const r = memoryRecordingStore([recording('4'), recording('5', REPLAY_COMPAT)])
    const result = await purgeStale(f, r, memory())
    expect(result).toEqual({ finished: ['LEON – 2', 'LEON – 1'], recordings: ['GRAB – 4'] })
    expect((await f.list()).map(m => m.code)).toEqual(['3'])
    expect((await r.list()).map(m => m.code)).toEqual(['5'])
  })

  it('does it once: the next start keeps whatever is there, even if it is old', async () => {
    const storage = memory()
    await purgeStale(memoryFinishedStore(), memoryRecordingStore(), storage)
    expect(storage.getItem(COMPAT_KEY)).toBe(String(REPLAY_COMPAT))
    const f = memoryFinishedStore([finished('1')])
    expect(await purgeStale(f, memoryRecordingStore(), storage)).toEqual({ finished: [], recordings: [] })
    expect((await f.list()).map(m => m.code)).toEqual(['1'])                 // kept: the list warns about it and offers to delete it (#562)
  })

  it('a device that already ran this compatibility is left alone', async () => {
    const f = memoryFinishedStore([finished('1', 1)])
    expect(await purgeStale(f, memoryRecordingStore(), memory({ [COMPAT_KEY]: String(REPLAY_COMPAT) }))).toEqual({ finished: [], recordings: [] })
    expect(await f.list()).toHaveLength(1)
  })

  it('a device that ran an older compatibility is cleaned when this one is raised', async () => {
    const f = memoryFinishedStore([finished('1', 2)])
    const storage = memory({ [COMPAT_KEY]: String(REPLAY_COMPAT - 1) })
    expect((await purgeStale(f, memoryRecordingStore(), storage)).finished).toEqual(['LEON – 1'])
    expect(storage.getItem(COMPAT_KEY)).toBe(String(REPLAY_COMPAT))
  })

  it('nothing on the device and a store that fails are not a crash, and the next start tries again', async () => {
    const broken = { ...memoryFinishedStore(), list: async () => { throw new Error('IndexedDB is not available') } }
    const storage = memory()
    expect(await purgeStale(broken, memoryRecordingStore(), storage)).toEqual({ finished: [], recordings: [] })
    expect(storage.getItem(COMPAT_KEY)).toBeNull()
  })
})
