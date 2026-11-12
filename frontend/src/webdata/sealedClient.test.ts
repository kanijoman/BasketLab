import { beforeEach, describe, expect, it } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { DataUnavailable } from '@/datasource/resolve'
import { createSealedClient, type SealedManifest } from './sealedClient'
import { LF2_KEY, readTalent, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'
import type { WebDataHost } from '@/test/webDataHost'

/** The generic part of the readers of a publication (#878): the manifest, the files that never change in place and the unlocking, tested against the REAL publication of Talent. */
class TestUnavailable extends DataUnavailable {}
interface Manifest extends SealedManifest { competitions: Array<{ key: string; file: string; wraps: Array<{ scope: string; iv: string; key: string }> }> }

let host: WebDataHost
const client = () => createSealedClient<Manifest>({ base: TALENT_BASE, schema: 1, unavailable: TestUnavailable })
beforeEach(() => { localStorage.clear(); host = serveTalentData() })

const entryOf = async (c: ReturnType<typeof client>) => (await c.loadManifest()).competitions.find(e => e.key === LF2_KEY)!

describe('the manifest', () => {
  it('is read once from index.json of the base and the promise is kept', async () => {
    const c = client()
    const [a, b] = await Promise.all([c.loadManifest(), c.loadManifest()])
    expect(a).toBe(b)
    expect(host.requested).toEqual(['index.json'])
  })

  it('a schema that is not the one of the reader is unavailable and says to update the page', async () => {
    host.override['index.json'] = JSON.stringify({ ...JSON.parse(readTalent('index.json')), schema: 99 })
    await expect(client().loadManifest()).rejects.toThrow(/no soportada/)
    await expect(client().loadManifest()).rejects.toBeInstanceOf(TestUnavailable)
  })

  it('a failed load is not remembered: the next one asks again', async () => {
    const c = client()
    host.override['index.json'] = null
    await expect(c.loadManifest()).rejects.toBeInstanceOf(TestUnavailable)
    delete host.override['index.json']
    expect((await c.loadManifest()).schema).toBe(1)
  })

  it('a base without the final slash gets it, and moving it forgets what was loaded', async () => {
    const c = client()
    await c.loadManifest()
    c.setBase('https://talent.test')
    await c.loadManifest()
    expect(host.requested).toEqual(['index.json', 'index.json'])
  })
})

describe('the sealed files', () => {
  it('open with the open key the manifest publishes', async () => {
    const c = client()
    const entry = await entryOf(c)
    const doc = await c.openSealed<{ rows: unknown[] }>(async () => ({ manifest: await c.loadManifest(), wraps: entry.wraps, text: await c.fetchText(entry.file) }), 'El fichero')
    expect(doc.rows.length).toBeGreaterThan(0)
  })

  it('a file that is gone makes it read the manifest again, once; twice means the data changed', async () => {
    const c = client()
    const entry = await entryOf(c)
    const locate = async () => ({ manifest: await c.loadManifest(), wraps: entry.wraps, text: await c.fetchText(entry.file) })
    host.override[entry.file] = null
    await expect(c.openSealed(locate, 'El fichero')).rejects.toThrow(/han cambiado/)
    expect(host.requested.filter(f => f === 'index.json')).toHaveLength(2)
  })

  it('without the open key and without rights there is no access, which is not "unavailable"', async () => {
    const manifest = JSON.parse(readTalent('index.json'))
    delete manifest.open_key
    host.override['index.json'] = JSON.stringify(manifest)
    const c = client()
    const entry = await entryOf(c)
    await expect(c.openSealed(async () => ({ manifest, wraps: entry.wraps, text: await c.fetchText(entry.file) }), 'El fichero')).rejects.toBeInstanceOf(ScopedAccessError)
  })

  it('a file that is not an envelope is reported damaged', async () => {
    const c = client()
    const entry = await entryOf(c)
    host.override[entry.file] = '{"not":"an envelope"}'
    await expect(c.openSealed(async () => ({ manifest: await c.loadManifest(), wraps: entry.wraps, text: await c.fetchText(entry.file) }), 'El fichero')).rejects.toThrow(/dañado/)
  })
})
