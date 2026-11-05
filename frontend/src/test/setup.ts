import '@testing-library/jest-dom'
import { afterEach, beforeEach, vi } from 'vitest'

// Node's own (experimental) localStorage global can shadow jsdom's and be unusable (Node ≥ 25): use an in-memory Storage, as the live app does.
class MemoryStorage implements Storage {
  private data = new Map<string, string>()
  get length() { return this.data.size }
  clear() { this.data.clear() }
  getItem(key: string) { return this.data.get(key) ?? null }
  key(index: number) { return [...this.data.keys()][index] ?? null }
  removeItem(key: string) { this.data.delete(key) }
  setItem(key: string, value: string) { this.data.set(key, String(value)) }
}
vi.stubGlobal('localStorage', new MemoryStorage())

// what a test stores (the theme chosen...) must not leak into the next one
afterEach(() => {
  try { localStorage.clear() } catch { /* not ours */ }
})

// Since #334 the default is the published files (see datasource/switch.ts). Most tests describe the API client or a page with its API mocked: they start on the API, and the
// ones about the local data (or about the default itself) say so with `?data=local` or by clearing this key.
// A test that calls `vi.unstubAllGlobals()` drops the in-memory storage above, so it is made again (and pinned) before every test.
beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage())
  try { localStorage.setItem('basketlab.data', 'api') } catch { /* not ours */ }
})
