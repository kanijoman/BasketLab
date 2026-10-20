/**
 * Decrypts the .bpkg envelope written by src/live_prep/package_crypto.py:
 *   {"v":1,"alg":"AES-256-GCM","kdf":"PBKDF2-SHA256","iterations":N,"salt","iv","ciphertext"}
 * (binary fields base64; ciphertext = data || 16-byte GCM tag). Uses WebCrypto only. A bundle of packages (issue #286) carries
 * `"z": "gzip"`: it was compressed BEFORE it was encrypted, so after decrypting it is inflated with the WebView's DecompressionStream.
 * A package sealed by scope (issue #410, src/live_prep/package_scopes.py) is `{"v":2,"alg","iv","ciphertext"[,"z"]}` with no derivation: its key
 * (CEK) is wrapped once per scope in the index entry (`wraps`) and `decryptScoped` opens it with the key of any scope the reader has.
 */
export class PackageDecryptError extends Error {}
/** A scoped package that this device cannot open (no right, or an invitation that does not work): the message already says what to do. */
export class ScopedAccessError extends PackageDecryptError {}

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
  z?: string
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
  if (env.z !== undefined && env.z !== 'gzip') throw new PackageDecryptError('Compresión del paquete no soportada. Actualiza la app.')
  const iterations = Number(env.iterations)
  if (!Number.isInteger(iterations) || iterations < 1 || iterations > MAX_ITERATIONS) {
    throw new PackageDecryptError('Número de iteraciones no soportado.')
  }
  return env as Envelope
}

async function gunzip(bytes: ArrayBuffer): Promise<ArrayBuffer> {
  const stream = new Response(bytes).body!.pipeThrough(new DecompressionStream('gzip'))
  return new Response(stream).arrayBuffer()
}

function fromBase64(value: string): Uint8Array {
  const bin = atob(value)
  return Uint8Array.from(bin, c => c.charCodeAt(0))
}

/** Like `decryptEnvelope`, for a password typed on a phone (issue #337): as typed first and, if that fails, without the spaces or line
 *  breaks a keyboard leaves at the start or the end. A password that really has them still works: it is tried first as typed. */
export async function decryptPackage(text: string, passphrase: string): Promise<string> {
  try {
    return await decryptEnvelope(text, passphrase)
  } catch (error) {
    const trimmed = passphrase.trim()
    if (error instanceof PackageDecryptError && trimmed !== passphrase && trimmed) return decryptEnvelope(text, trimmed)
    throw error
  }
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
    return new TextDecoder().decode(env.z === 'gzip' ? await gunzip(plain) : plain)
  } catch {
    throw new PackageDecryptError('No se pudo descifrar: contraseña incorrecta o fichero dañado. Usa la que fijó quien genera los paquetes.')
  }
}

/** The CEK of a scoped package, wrapped with the key of one scope (authenticated with the scope name). */
export interface Wrap {
  scope: string
  iv: string
  key: string
}

/** The key (32 bytes) of a scope the reader has: the published open one or the one of an invitation. */
export interface ScopeKey {
  scope: string
  key: Uint8Array
}

const SCOPED_VERSION = 2

/** Is this file sealed by scope (v2) rather than by password (v1)? */
export function isScoped(text: string): boolean {
  try {
    return JSON.parse(text)?.v === SCOPED_VERSION
  } catch {
    return false
  }
}

async function unwrap(subtle: SubtleCrypto, wrap: Wrap, key: Uint8Array): Promise<ArrayBuffer | null> {
  try {
    const material = await subtle.importKey('raw', key as BufferSource, 'AES-GCM', false, ['decrypt'])
    return await subtle.decrypt({ name: 'AES-GCM', iv: fromBase64(wrap.iv) as BufferSource, additionalData: new TextEncoder().encode(wrap.scope) },
      material, fromBase64(wrap.key) as BufferSource)
  } catch {
    return null
  }
}

/** Returns the plaintext of a package sealed by scope, opened with the first wrap whose scope the reader has a key for. */
export async function decryptScoped(text: string, wraps: Wrap[], keys: ScopeKey[]): Promise<string> {
  let env: Partial<Envelope>
  try {
    env = JSON.parse(text)
  } catch {
    throw new PackageDecryptError('El fichero no es un paquete de BasketLab (no es JSON válido).')
  }
  if (!env || typeof env !== 'object' || !env.iv || !env.ciphertext || env.v === undefined) throw new PackageDecryptError('El fichero no es un paquete de BasketLab.')
  if (env.v !== SCOPED_VERSION) throw new PackageDecryptError(`Versión de paquete no soportada (${env.v}). Actualiza la app.`)
  if (env.alg !== 'AES-256-GCM') throw new PackageDecryptError('Algoritmo de cifrado no soportado.')
  if (env.z !== undefined && env.z !== 'gzip') throw new PackageDecryptError('Compresión del paquete no soportada. Actualiza la app.')
  const subtle = globalThis.crypto.subtle
  const mine = (wraps ?? []).filter(w => keys.some(k => k.scope === w.scope))
  if (mine.length === 0) throw new ScopedAccessError('No tienes acceso a este partido: pega una invitación (clave o enlace) en Partidos.')
  let cek: ArrayBuffer | null = null
  for (const wrap of mine) {
    for (const k of keys.filter(k => k.scope === wrap.scope)) {
      cek = await unwrap(subtle, wrap, k.key)
      if (cek) break
    }
    if (cek) break
  }
  if (!cek) throw new ScopedAccessError('No se pudo abrir el partido: la invitación no es válida o ha caducado.')
  try {
    const material = await subtle.importKey('raw', cek, 'AES-GCM', false, ['decrypt'])
    const plain = await subtle.decrypt({ name: 'AES-GCM', iv: fromBase64(env.iv) as BufferSource }, material, fromBase64(env.ciphertext) as BufferSource)
    return new TextDecoder().decode(env.z === 'gzip' ? await gunzip(plain) : plain)
  } catch {
    throw new PackageDecryptError('No se pudo abrir el partido: el fichero está dañado. Reintenta en unos minutos.')
  }
}
