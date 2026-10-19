/** A small keyed store of what a match leaves on the device (issues #407, #416): items by code, newest first, only the latest few kept.
 *  IndexedDB for the app, memory for tests, and a wrapper that never fails when IndexedDB is unavailable (private mode). */
export interface Keyed { code: string; savedAt: string }

export interface KeyedStore<T extends Keyed> {
  /** Newest first. */
  list(): Promise<T[]>
  load(code: string): Promise<T | null>
  /** Saves (replacing the same code) and drops the oldest beyond the limit of the store. */
  save(item: T): Promise<void>
}

const newestFirst = <T extends Keyed>(all: T[]): T[] => [...all].sort((a, b) => b.savedAt.localeCompare(a.savedAt))

function request<R>(req: IDBRequest<R>): Promise<R> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export class IndexedDbKeyedStore<T extends Keyed> implements KeyedStore<T> {
  private db: Promise<IDBDatabase> | null = null

  constructor(private readonly name: string, private readonly table: string, private readonly limit: number) {}

  private open(): Promise<IDBDatabase> {
    this.db ??= new Promise((resolve, reject) => {
      const req = indexedDB.open(this.name, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(this.table, { keyPath: 'code' })
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
    return this.db
  }

  private async store(mode: IDBTransactionMode): Promise<IDBObjectStore> {
    return (await this.open()).transaction(this.table, mode).objectStore(this.table)
  }

  async list(): Promise<T[]> {
    return newestFirst((await request((await this.store('readonly')).getAll())) as T[])
  }

  async load(code: string): Promise<T | null> {
    return ((await request((await this.store('readonly')).get(code))) as T | undefined) ?? null
  }

  async save(item: T): Promise<void> {
    await request((await this.store('readwrite')).put(item))
    for (const old of (await this.list()).slice(this.limit)) await request((await this.store('readwrite')).delete(old.code))
  }
}

export function memoryKeyedStore<T extends Keyed>(limit: number, initial: T[] = []): KeyedStore<T> {
  const all = new Map(initial.map(m => [m.code, m]))
  return {
    list: async () => newestFirst([...all.values()]),
    load: async code => all.get(code) ?? null,
    save: async item => {
      all.set(item.code, item)
      for (const old of newestFirst([...all.values()]).slice(limit)) all.delete(old.code)
    },
  }
}

/** A store that never fails when the storage is unavailable: it lists nothing and forgets what it is given. */
export function safeKeyedStore<T extends Keyed>(inner: KeyedStore<T>): KeyedStore<T> {
  return {
    list: () => inner.list().catch(() => []),
    load: code => inner.load(code).catch(() => null),
    save: item => inner.save(item).catch(() => undefined),
  }
}
