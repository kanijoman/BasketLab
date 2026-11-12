// The generic part of the readers of a publication (issues #328, #639, #878): a static host with no server, a manifest `index.json` that is the only file keeping its name, and sealed files whose
// name carries the hash of their content, opened with the open key the manifest publishes while the beta lasts and with the rights (invitations) of the reader. `web-data` (Analytics, `client.ts`) and
// `talent-data` (Talent, `market/data.ts`) are two publications with their own manifest and branch and use the same code. Unlocking is the live app's (`@live-package`): one implementation until
// the shared interface (#330). Everything answers with the `unavailable` error of its publication when the data cannot be had and lets `ScopedAccessError` through: «you have no key for this»
// is not «try again».
import { decryptScoped, PackageDecryptError, ScopedAccessError } from '@live-package/crypto'
import { loadRights, scopeKeys } from '@live-package/rights'
import type { Wrap } from './contract.generated'

export interface SealedManifest { schema: number; v: number; open_key?: string }

/** A sealed file of a publication with the manifest it came from, the wraps of its key and its text. */
export interface Sealed<M extends SealedManifest> { manifest: M; wraps: Wrap[]; text: string }

/** 404: the file of a publication that has been replaced. */
export class Gone extends Error {}

export interface SealedClientOptions {
  /** Where the publication is (a URL ending in `/`). */
  base: string
  /** The schema of the manifest this reader understands. */
  schema: number
  /** The error of the publication ("it cannot be had"): the callers say there is no answer instead of asking something else. */
  unavailable: new (message: string) => Error
}

export function createSealedClient<M extends SealedManifest>(options: SealedClientOptions) {
  const Unavailable = options.unavailable
  let base = options.base
  let manifestLoad: Promise<M> | null = null
  const resets: Array<() => void> = []

  /** Forget what was loaded (tests, a manifest that was replaced); `onReset` lets a reader forget its own caches too. */
  function reset(): void {
    manifestLoad = null
    for (const fn of resets) fn()
  }

  /** Where the publication is (tests, or a host other than the default). */
  function setBase(url: string): void {
    base = url.endsWith('/') ? url : `${url}/`
    reset()
  }

  async function fetchText(file: string): Promise<string> {
    let res: Response
    try {
      res = await fetch(base + file)
    } catch {
      throw new Unavailable('No se pudo conectar con los datos publicados.')
    }
    if (res.status === 404) throw new Gone(file)
    if (!res.ok) throw new Unavailable(`Los datos publicados no responden (HTTP ${res.status}).`)
    return res.text()
  }

  async function fetchJson<T>(file: string): Promise<T> {
    try {
      return JSON.parse(await fetchText(file)) as T
    } catch (error) {
      if (error instanceof Gone) throw new Unavailable('Los datos publicados no están disponibles.')
      if (error instanceof Unavailable) throw error
      throw new Unavailable('Los datos publicados están dañados.')
    }
  }

  function loadManifest(): Promise<M> {
    if (!manifestLoad) {
      manifestLoad = fetchJson<M>('index.json').then(manifest => {
        if (manifest?.schema !== options.schema) throw new Unavailable(`Versión de los datos publicados no soportada (${manifest?.schema}). Actualiza la página.`)
        return manifest
      })
      manifestLoad.catch(() => { manifestLoad = null })           // a failed load is not remembered
    }
    return manifestLoad
  }

  /**
   * Opens a sealed file of the publication with the open key and the rights of the reader. A file that is gone (the publication moved on while the page was open) makes it read the manifest
   * again, once.
   * @throws ScopedAccessError the reader has no key that opens it (ask for an invitation)
   * @throws the `unavailable` error of the publication: it cannot be had
   */
  async function openSealed<T>(locate: () => Promise<Sealed<M>>, what: string): Promise<T> {
    let sealed
    try {
      sealed = await locate()
    } catch (error) {
      if (!(error instanceof Gone)) throw error
      reset()
      try {
        sealed = await locate()
      } catch (again) {
        throw again instanceof Gone ? new Unavailable('Los datos publicados han cambiado: recarga la página.') : again
      }
    }
    try {
      return JSON.parse(await decryptScoped(sealed.text, sealed.wraps, scopeKeys(sealed.manifest, loadRights()))) as T
    } catch (error) {
      if (error instanceof ScopedAccessError) throw error
      if (error instanceof PackageDecryptError || error instanceof SyntaxError) throw new Unavailable(`${what} publicado está dañado.`)
      throw error
    }
  }

  return { setBase, reset, onReset: (fn: () => void) => { resets.push(fn) }, fetchText, fetchJson, loadManifest, openSealed }
}
