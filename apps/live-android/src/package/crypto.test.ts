// @vitest-environment node
// WebCrypto decryption of the Python-produced .bpkg: tested against the very bytes that
// tests/test_live_prep_crypto.py decrypts with Python (tests/live_vectors/demo.bpkg).
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { PackageDecryptError, decryptEnvelope } from './crypto'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const fixture = fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo.bpkg'), 'utf8')
const demoPackage: string = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/vectors.json'), 'utf8')).engine.package
const PASS = 'clave-de-prueba-1'

describe('decryptEnvelope (AES-256-GCM, PBKDF2-SHA256)', () => {
  it('decrypts what Python encrypted, byte for byte', async () => {
    expect(await decryptEnvelope(fixture, PASS)).toBe(demoPackage)
  })

  it('rejects a wrong passphrase with a clear message', async () => {
    await expect(decryptEnvelope(fixture, 'otra-clave-distinta')).rejects.toThrow(PackageDecryptError)
    await expect(decryptEnvelope(fixture, 'otra-clave-distinta')).rejects.toThrow(/contraseña/i)
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
