import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { IndexedDbPackageStore, type StoredPackage } from './storage'

const record = (name: string): StoredPackage => ({
  plaintext: `{"checksum":"x","package":{"team":{"name":"${name}"}}}`,
  savedAt: '2026-10-09T10:00:00Z',
})

describe('IndexedDbPackageStore', () => {
  let store: IndexedDbPackageStore
  beforeEach(() => {
    store = new IndexedDbPackageStore(`test-${Math.random()}`)
  })

  it('returns null when nothing was saved', async () => {
    expect(await store.load()).toBeNull()
  })

  it('saves and loads the package on this device', async () => {
    await store.save(record('A'))
    expect(await store.load()).toEqual(record('A'))
  })

  it('keeps a single package: saving replaces the previous one', async () => {
    await store.save(record('A'))
    await store.save(record('B'))
    expect((await store.load())!.plaintext).toContain('"B"')
  })

  it('clears the package', async () => {
    await store.save(record('A'))
    await store.clear()
    expect(await store.load()).toBeNull()
  })

  it('persists across store instances (same database)', async () => {
    const name = `persist-${Math.random()}`
    await new IndexedDbPackageStore(name).save(record('A'))
    expect(await new IndexedDbPackageStore(name).load()).toEqual(record('A'))
  })
})
