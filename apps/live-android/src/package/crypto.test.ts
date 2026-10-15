// @vitest-environment node
// WebCrypto decryption of the Python-produced .bpkg: tested against the very bytes that
// tests/test_live_prep_crypto.py decrypts with Python (tests/live_vectors/demo.bpkg).
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { PackageDecryptError, decryptEnvelope, decryptPackage } from './crypto'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const fixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo.bpkg'), 'utf8')
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const PASS = 'clave-de-prueba-1'

describe('decryptPackage: the password as it is typed on a phone (issue #337)', () => {
  it('accepts it as typed', async () => {
    expect(await decryptPackage(fixture, PASS)).toBe(demoPackage)
  })

  it('and also with the spaces a keyboard adds at the start or the end', async () => {
    expect(await decryptPackage(fixture, `  ${PASS} `)).toBe(demoPackage)
    expect(await decryptPackage(fixture, `${PASS}\n`)).toBe(demoPackage)
  })

  it('a wrong password still fails with the same clear message', async () => {
    await expect(decryptPackage(fixture, ' otra-clave-distinta ')).rejects.toThrow(PackageDecryptError)
    await expect(decryptPackage(fixture, 'otra-clave-distinta')).rejects.toThrow(/contraseña/i)
  })

  it('a password whose spaces are part of it still works as typed', async () => {
    // the as-typed attempt comes first: nothing is trimmed away from a password that was right
    expect(await decryptPackage(fixture, PASS)).toBe(demoPackage)
  })
})

const roundFixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_round.bpkgz'), 'utf8')

describe('compressed bundles (issue #286)', () => {
  it('decrypts and decompresses what Python wrote (gzip before AES-GCM)', async () => {
    expect(JSON.parse(roundFixture).z).toBe('gzip')
    const bundle = JSON.parse(await decryptEnvelope(roundFixture, PASS))
    expect(bundle.collection).toBe('DEMO_2026')
    expect(bundle.matches.map((m: { match: { code: string } }) => m.match.code)).toEqual(['101', '101', '102', '102', '103', '103'])   // each match from both of its teams
    expect(bundle.matches[0].package).toBe(demoPackage)
  })

  it('refuses a compression it does not know', async () => {
    await expect(decryptEnvelope(JSON.stringify({ ...JSON.parse(roundFixture), z: 'brotli' }), PASS)).rejects.toThrow(/compresión/i)
  })

  it('a wrong passphrase still fails as before', async () => {
    await expect(decryptEnvelope(roundFixture, 'otra-clave-distinta')).rejects.toThrow(/contraseña/i)
  })
})

describe('decryptEnvelope (AES-256-GCM, PBKDF2-SHA256)', () => {
  it('decrypts what Python encrypted, byte for byte', async () => {
    expect(await decryptEnvelope(fixture, PASS)).toBe(demoPackage)
  })

  it('rejects a wrong passphrase with a clear message', async () => {
    await expect(decryptEnvelope(fixture, 'otra-clave-distinta')).rejects.toThrow(PackageDecryptError)
    await expect(decryptEnvelope(fixture, 'otra-clave-distinta')).rejects.toThrow(/contraseña/i)
    await expect(decryptEnvelope(fixture, 'otra-clave-distinta')).rejects.toThrow(/quien genera los paquetes/i)  // what to do (#225)
  })

  it('rejects tampered data (GCM authentication)', async () => {
    const env = JSON.parse(fixture)
    const raw = Buffer.from(env.ciphertext, 'base64')
    raw[10] ^= 0xff
    env.ciphertext = raw.toString('base64')
    await expect(decryptEnvelope(JSON.stringify(env), PASS)).rejects.toThrow(PackageDecryptError)
  })

  it('rejects files that are not a package envelope', async () => {
    await expect(decryptEnvelope('not json', PASS)).rejects.toThrow(/no es un paquete/i)
    await expect(decryptEnvelope('{"hello":1}', PASS)).rejects.toThrow(/no es un paquete/i)
  })

  it('rejects an unsupported envelope version or algorithm', async () => {
    const env = { ...JSON.parse(fixture), v: 2 }
    await expect(decryptEnvelope(JSON.stringify(env), PASS)).rejects.toThrow(/versión|no soportado/i)
    const env2 = { ...JSON.parse(fixture), alg: 'AES-128-CBC' }
    await expect(decryptEnvelope(JSON.stringify(env2), PASS)).rejects.toThrow(/no soportado/i)
  })

  it('refuses absurd iteration counts instead of freezing the device', async () => {
    const env = { ...JSON.parse(fixture), iterations: 5_000_000_000 }
    await expect(decryptEnvelope(JSON.stringify(env), PASS)).rejects.toThrow(/no soportado|iteraciones/i)
  })
})
