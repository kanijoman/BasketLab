import { beforeEach, describe, expect, it } from 'vitest'
import { clearPassphrase, loadPassphrase, savePassphrase } from './passphrase'

beforeEach(() => localStorage.clear())

describe('passphrase', () => {
  it('is remembered once and read back', () => {
    expect(loadPassphrase()).toBe('')
    savePassphrase('clave-larga-123')
    expect(loadPassphrase()).toBe('clave-larga-123')
    clearPassphrase()
    expect(loadPassphrase()).toBe('')
  })

  it('never throws when storage is unavailable', () => {
    const broken = {
      getItem() { throw new Error('x') }, setItem() { throw new Error('x') }, removeItem() { throw new Error('x') },
    } as unknown as Storage
    expect(loadPassphrase(broken)).toBe('')
    expect(() => savePassphrase('a', broken)).not.toThrow()
  })
})
