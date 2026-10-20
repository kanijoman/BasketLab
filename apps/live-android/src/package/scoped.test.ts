// @vitest-environment node
// Packages sealed by scope (issue #410): WebCrypto against the very bytes Python wrote (tests/live_vectors/demo_scoped.json).
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { PackageDecryptError, decryptScoped, isScoped } from './crypto'
import { parseInvite } from './rights'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const demo = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_scoped.json'), 'utf8'))
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const b64 = (text: string) => Uint8Array.from(atob(text), c => c.charCodeAt(0))
const open = { scope: 'abierto', key: b64(demo.open_key) }
const club = () => { const r = parseInvite(demo.invitations['club:1008631'].token); return { scope: r.scope, key: b64url(r.key) } }
const b64url = (text: string) => Uint8Array.from(atob(text.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0))

describe('decryptScoped', () => {
  it('opens a package with the key of the open scope that the index publishes', async () => {
    expect(await decryptScoped(demo.package.file, demo.package.wraps, [open])).toBe(demoPackage)
  })

  it('opens it with the key of an invitation to another scope of the wraps', async () => {
    expect(await decryptScoped(demo.package.file, demo.package.wraps, [club()])).toBe(demoPackage)
  })

  it('opens a compressed round bundle (gzip before AES-GCM)', async () => {
    expect(await decryptScoped(demo.round.file, demo.round.wraps, [open])).toBe(demo.round.plaintext)
  })

  it('says there is no access when no key of the reader is among the wraps', async () => {
    const other = parseInvite(demo.invitations['club:999'].token)
    await expect(decryptScoped(demo.package.file, demo.package.wraps, [])).rejects.toThrow(/acceso/i)
    await expect(decryptScoped(demo.package.file, demo.package.wraps, [{ scope: other.scope, key: b64url(other.key) }])).rejects.toThrow(PackageDecryptError)
  })

  it('a key under the right scope name that is not the real one does not open it', async () => {
    await expect(decryptScoped(demo.package.file, demo.package.wraps, [{ scope: 'abierto', key: new Uint8Array(32) }])).rejects.toThrow(PackageDecryptError)
  })

  it('a wrap moved under another scope name does not open (the scope is authenticated)', async () => {
    const forged = demo.package.wraps.map((w: { scope: string }) => ({ ...w, scope: w.scope === 'abierto' ? 'club:999' : w.scope }))
    const other = parseInvite(demo.invitations['club:999'].token)
    await expect(decryptScoped(demo.package.file, forged, [{ scope: other.scope, key: b64url(other.key) }])).rejects.toThrow(PackageDecryptError)
  })

  it('rejects tampered data and files that are not a scoped package', async () => {
    const env = JSON.parse(demo.package.file)
    const raw = Buffer.from(env.ciphertext, 'base64')
    raw[10] ^= 0xff
    await expect(decryptScoped(JSON.stringify({ ...env, ciphertext: raw.toString('base64') }), demo.package.wraps, [open])).rejects.toThrow(PackageDecryptError)
    await expect(decryptScoped('not json', demo.package.wraps, [open])).rejects.toThrow(/no es un paquete/i)
    await expect(decryptScoped(JSON.stringify({ ...env, v: 1 }), demo.package.wraps, [open])).rejects.toThrow(/versión/i)
    await expect(decryptScoped(JSON.stringify({ ...env, z: 'brotli' }), demo.package.wraps, [open])).rejects.toThrow(/compresión/i)
  })

  it('tells a scoped file from a password one', () => {
    expect(isScoped(demo.package.file)).toBe(true)
    expect(isScoped(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo.bpkg'), 'utf8'))).toBe(false)
    expect(isScoped('not json')).toBe(false)
  })
})
