import type { LoggedAlert } from '../engine/types'

/** Finished live matches kept on the device (issue #407), so the staff can review them later without the app being connected.
 *  What is kept is the package the match was followed with and the last merged FEB document (it has the whole play-by-play):
 *  the review replays it through the engine like the sample game. About 1 MB each, hence the limit. */
export interface FinishedMatch {
  /** FEB match code. */
  code: string
  /** "Local – Visitante". */
  title: string
  savedAt: string
  /** Id of the own team: the post-match report is built from its point of view (issue #409). */
  ownId: string
  /** Every alert the engine raised during the match, with the clock label it was shown at: the annex of the report (#409). */
  alerts: LoggedAlert[]
  /** The preparation package (decrypted JSON text) of the match. */
  plaintext: string
  /** The last merged FEB document (JSON text). */
  game: string
}

export interface FinishedStore {
  /** Newest first. */
  list(): Promise<FinishedMatch[]>
  load(code: string): Promise<FinishedMatch | null>
  /** Saves (replacing the same code) and drops the oldest beyond ``MAX_FINISHED``. */
  save(match: FinishedMatch): Promise<void>
}

export const MAX_FINISHED = 5

const STORE = 'matches'

const newestFirst = (all: FinishedMatch[]) => [...all].sort((a, b) => b.savedAt.localeCompare(a.savedAt))

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export class IndexedDbFinishedStore implements FinishedStore {
  private db: Promise<IDBDatabase> | null = null

  constructor(private readonly name = 'basketlab-live-finished') {}

  private open(): Promise<IDBDatabase> {
    this.db ??= new Promise((resolve, reject) => {
      const req = indexedDB.open(this.name, 1)
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'code' })
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
    return this.db
  }

  private async store(mode: IDBTransactionMode): Promise<IDBObjectStore> {
    return (await this.open()).transaction(STORE, mode).objectStore(STORE)
  }

  async list(): Promise<FinishedMatch[]> {
    return newestFirst((await request((await this.store('readonly')).getAll())) as FinishedMatch[])
  }

  async load(code: string): Promise<FinishedMatch | null> {
    return ((await request((await this.store('readonly')).get(code))) as FinishedMatch | undefined) ?? null
  }

  async save(match: FinishedMatch): Promise<void> {
    await request((await this.store('readwrite')).put(match))
    for (const old of (await this.list()).slice(MAX_FINISHED)) await request((await this.store('readwrite')).delete(old.code))
  }
}

export function memoryFinishedStore(initial: FinishedMatch[] = []): FinishedStore {
  const all = new Map(initial.map(m => [m.code, m]))
  return {
    list: async () => newestFirst([...all.values()]),
    load: async code => all.get(code) ?? null,
    save: async match => {
      all.set(match.code, match)
      for (const old of newestFirst([...all.values()]).slice(MAX_FINISHED)) all.delete(old.code)
    },
  }
}

/** A store that never fails when IndexedDB is unavailable (private mode, tests): it lists nothing and forgets what it is given. */
export function safeFinishedStore(inner: FinishedStore): FinishedStore {
  return {
    list: () => inner.list().catch(() => []),
    load: code => inner.load(code).catch(() => null),
    save: match => inner.save(match).catch(() => undefined),
  }
}
