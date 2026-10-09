/**
 * Decrypts the .bpkg envelope written by src/live_prep/package_crypto.py:
 *   {"v":1,"alg":"AES-256-GCM","kdf":"PBKDF2-SHA256","iterations":N,"salt","iv","ciphertext"}
 * (binary fields base64; ciphertext = data || 16-byte GCM tag). Uses WebCrypto only.
 */
export class PackageDecryptError extends Error {}

const ENVELOPE_VERSION = 1
const MAX_ITERATIONS = 5_000_000 // refuse absurd values (a hostile file could freeze the device)

interface Envelope {
  v: number
  alg: string
  kdf: string
  iterations: number
  salt: string
  iv: string
  ciphertext: string
}

function parseEnvelope(text: string): Envelope {
  let env: Partial<Envelope>
  try {
    env = JSON.parse(text)
  } catch {
    throw new PackageDecryptError('El fichero no es un paquete de BasketLab (no es JSON válido).')
  }
  if (!env || typeof env !== 'object' || !env.salt || !env.iv || !env.ciphertext || env.v === undefined) {
    throw new PackageDecryptError('El fichero no es un paquete de BasketLab.')
  }
  if (env.v !== ENVELOPE_VERSION) throw new PackageDecryptError(`Versión de paquete no soportada (${env.v}). Actualiza la app.`)
  if (env.alg !== 'AES-256-GCM' || env.kdf !== 'PBKDF2-SHA256') {
    throw new PackageDecryptError('Algoritmo de cifrado no soportado.')
  }
  const iterations = Number(env.iterations)
  if (!Number.isInteger(iterations) || iterations < 1 || iterations > MAX_ITERATIONS) {
    throw new PackageDecryptError('Número de iteraciones no soportado.')
  }
  return env as Envelope
}

function fromBase64(value: string): Uint8Array {
  const bin = atob(value)
  return Uint8Array.from(bin, c => c.charCodeAt(0))
}

/** Returns the package JSON text (the PreparationPackage envelope with its own checksum). */
export async function decryptEnvelope(text: string, passphrase: string): Promise<string> {
  const env = parseEnvelope(text)
  try {
    const subtle = globalThis.crypto.subtle
    const material = await subtle.importKey('raw', new TextEncoder().encode(passphrase), 'PBKDF2', false, ['deriveKey'])
    const key = await subtle.deriveKey(
      { name: 'PBKDF2', hash: 'SHA-256', salt: fromBase64(env.salt) as BufferSource, iterations: Number(env.iterations) },
      material, { name: 'AES-GCM', length: 256 }, false, ['decrypt'],
    )
    const plain = await subtle.decrypt(
      { name: 'AES-GCM', iv: fromBase64(env.iv) as BufferSource }, key, fromBase64(env.ciphertext) as BufferSource,
    )
    return new TextDecoder().decode(plain)
  } catch {
    throw new PackageDecryptError('No se pudo descifrar: contraseña incorrecta o fichero dañado.')
  }
}
