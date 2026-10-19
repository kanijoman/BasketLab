import 'fake-indexeddb/auto'
import { describe, expect, it } from 'vitest'
import { IndexedDbRecordingStore, MAX_RECORDINGS, decodeRecording, encodeRecording, memoryRecordingStore, type SavedRecording } from './recordingStore'

const saved = (code: string, savedAt: string, bytes = new Uint8Array([1, 2, 3])): SavedRecording =>
  ({ code, title: `Local ${code} – Visitante`, savedAt, complete: true, frames: 10, encoding: 'raw', bytes })

describe('recordings kept on the device (issue #416)', () => {
  it('gzips the recording like the files of the repository and reads it back', async () => {
    const text = JSON.stringify({ v: 1, lines: Array.from({ length: 200 }, (_, i) => ({ num: String(i), text: 'Tiro de 2 anotado' })) })
    const { encoding, bytes } = await encodeRecording(text)
    expect(encoding).toBe('gzip')
    expect([bytes[0], bytes[1]]).toEqual([0x1f, 0x8b])                 // the magic number RecordedFeed.loads looks for
    expect(bytes.length).toBeLessThan(text.length / 4)
    expect(await decodeRecording({ encoding, bytes })).toBe(text)
  })

  it('keeps the text as it is when the platform cannot compress', async () => {
    const original = globalThis.CompressionStream
    // @ts-expect-error a platform without CompressionStream
    globalThis.CompressionStream = undefined
    try {
      const { encoding, bytes } = await encodeRecording('{"v":1}')
      expect(encoding).toBe('raw')
      expect(await decodeRecording({ encoding, bytes })).toBe('{"v":1}')
    } finally {
      globalThis.CompressionStream = original
    }
  })

  describe.each([
    ['IndexedDB', () => new IndexedDbRecordingStore(`recordings-${Math.random()}`)],
    ['memory', () => memoryRecordingStore()],
  ])('store (%s)', (_name, make) => {
    it('lists the newest first, loads by code and replaces the same match', async () => {
      const store = make()
      await store.save(saved('1', '2026-10-17T20:00:00Z'))
      await store.save(saved('2', '2026-10-18T20:00:00Z'))
      await store.save({ ...saved('1', '2026-10-19T20:00:00Z'), complete: false, frames: 99 })
      const all = await store.list()
      expect(all.map(r => r.code)).toEqual(['1', '2'])
      expect((await store.load('1'))).toMatchObject({ complete: false, frames: 99 })
    })

    it('keeps only the latest recordings', async () => {
      const store = make()
      for (let i = 0; i < MAX_RECORDINGS + 2; i++) await store.save(saved(String(i), `2026-10-${10 + i}T20:00:00Z`))
      const codes = (await store.list()).map(r => r.code)
      expect(codes).toHaveLength(MAX_RECORDINGS)
      expect(codes).not.toContain('0')
    })
  })
})
