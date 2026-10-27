import '@testing-library/jest-dom'
import { afterEach, vi } from 'vitest'

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
