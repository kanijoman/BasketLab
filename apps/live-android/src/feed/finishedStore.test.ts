import 'fake-indexeddb/auto'
import { describe, expect, it } from 'vitest'
import { IndexedDbFinishedStore, MAX_FINISHED, memoryFinishedStore, safeFinishedStore, type FinishedMatch } from './finishedStore'

const match = (code: string, savedAt: string): FinishedMatch => ({
  code, title: `Local ${code} – Visitante`, savedAt, ownId: '1', alerts: [], plaintext: `PKG-${code}`, game: JSON.stringify({ PLAYBYPLAY: { LINES: [] }, code }),
})

describe.each([
  ['IndexedDB', () => new IndexedDbFinishedStore(`finished-${Math.random()}`)],
  ['memory', () => memoryFinishedStore()],
])('finished matches store (%s, issue #407)', (_name, make) => {
  it('lists the saved matches newest first and loads one by its code', async () => {
    const store = make()
    await store.save(match('1', '2026-10-17T20:00:00Z'))
    await store.save(match('2', '2026-10-18T20:00:00Z'))
    expect((await store.list()).map(m => m.code)).toEqual(['2', '1'])
    expect((await store.load('1'))?.plaintext).toBe('PKG-1')
    expect(await store.load('nope')).toBeNull()
  })

  it('saving the same match again replaces it instead of duplicating it', async () => {
    const store = make()
    await store.save(match('1', '2026-10-17T20:00:00Z'))
    await store.save({ ...match('1', '2026-10-18T20:00:00Z'), game: '{"v":2}' })
    const all = await store.list()
    expect(all).toHaveLength(1)
    expect(all[0].game).toBe('{"v":2}')
  })

  it('keeps only the latest matches: a document of a match weighs about 1 MB', async () => {
    const store = make()
    for (let i = 0; i < MAX_FINISHED + 2; i++) await store.save(match(String(i), `2026-10-1${i}T20:00:00Z`.replace(/1(\d)T/, (_m, d) => `${10 + Number(d)}T`)))
    const codes = (await store.list()).map(m => m.code)
    expect(codes).toHaveLength(MAX_FINISHED)
    expect(codes).not.toContain('0')
    expect(codes).toContain(String(MAX_FINISHED + 1))
  })
})

describe('safeFinishedStore', () => {
  it('never throws when the storage is unavailable', async () => {
    const broken = { list: () => Promise.reject(new Error('x')), load: () => Promise.reject(new Error('x')), save: () => Promise.reject(new Error('x')) }
    const store = safeFinishedStore(broken)
    expect(await store.list()).toEqual([])
    expect(await store.load('1')).toBeNull()
    await expect(store.save(match('1', '2026-10-17T20:00:00Z'))).resolves.toBeUndefined()
  })
})
