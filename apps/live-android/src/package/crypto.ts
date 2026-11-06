/**
 * Opens a package sealed by scope (issue #410, src/live_prep/package_scopes.py): `{"v":2,"alg":"AES-256-GCM","iv","ciphertext"[,"z"]}`
 * (binary fields base64; ciphertext = data || 16-byte GCM tag). Its key (CEK) is wrapped once per scope in the index entry (`wraps`) and
 * `decryptScoped` opens it with the key of any scope the reader has. A bundle of packages (issue #286) carries `"z": "gzip"`: it was
 * compressed BEFORE it was encrypted, so after decrypting it is inflated with the WebView's DecompressionStream. Uses WebCrypto only.
 * The password envelope (v1) is no longer read: nobody types a password in the app.
 */
export class PackageDecryptError extends Error {}
/** A scoped package that this device cannot open (no right, or an invitation that does not work): the message already says what to do. */
export class ScopedAccessError extends PackageDecryptError {}

interface Envelope {
  v: number
  alg: string
  iv: string
  ciphertext: string
  z?: string
}

async function gunzip(bytes: ArrayBuffer): Promise<ArrayBuffer> {
  const stream = new Response(bytes).body!.pipeThrough(new DecompressionStream('gzip'))
  return new Response(stream).arrayBuffer()
}

function fromBase64(value: string): Uint8Array {
  const bin = atob(value)
  return Uint8Array.from(bin, c => c.charCodeAt(0))
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

/** Is this file sealed by scope (v2)? Anything else is the old password format, which the app no longer opens. */
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

/** The message of a failed download or decryption. */
export function failureText(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
