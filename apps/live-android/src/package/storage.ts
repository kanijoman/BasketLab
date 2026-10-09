/** Keeps the imported preparation package on the device (IndexedDB, private to the app). */
export interface StoredPackage {
  /** The decrypted package JSON text (validated by the engine before saving). */
  plaintext: string
  savedAt: string
}

export interface PackageStore {
  load(): Promise<StoredPackage | null>
  save(record: StoredPackage): Promise<void>
  clear(): Promise<void>
}

const STORE = 'package'
const KEY = 'current'

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export class IndexedDbPackageStore implements PackageStore {
  private db: Promise<IDBDatabase> | null = null

  constructor(private readonly name = 'basketlab-live') {}

  private open(): Promise<IDBDatabase> {
    this.db ??= new Promise((resolve, reject) => {
      const req = indexedDB.open(this.name, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(STORE)
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
    return this.db
  }

  private async store(mode: IDBTransactionMode): Promise<IDBObjectStore> {
    return (await this.open()).transaction(STORE, mode).objectStore(STORE)
  }

  async load(): Promise<StoredPackage | null> {
    return ((await request((await this.store('readonly')).get(KEY))) as StoredPackage | undefined) ?? null
  }

  async save(record: StoredPackage): Promise<void> {
    await request((await this.store('readwrite')).put(record, KEY))
  }

  async clear(): Promise<void> {
    await request((await this.store('readwrite')).delete(KEY))
  }
}

/** Store that never fails when IndexedDB is unavailable (private mode, tests). */
export function safeStore(inner: PackageStore): PackageStore {
  return {
    load: () => inner.load().catch(() => null),
    save: r => inner.save(r),
    clear: () => inner.clear().catch(() => undefined),
  }
}
