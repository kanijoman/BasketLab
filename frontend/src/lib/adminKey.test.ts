import { beforeEach, describe, expect, it, vi } from 'vitest'
import { adminHeaders, clearAdminKey, getAdminKey, setAdminKey } from './adminKey'

describe('admin key storage', () => {
  beforeEach(() => sessionStorage.clear())

  it('stores the key for the browser session only', () => {
    setAdminKey('  s3cret  ')
    expect(getAdminKey()).toBe('s3cret')
    expect(sessionStorage.getItem('basketlab-admin-key')).toBe('s3cret')
  })

  it('builds the X-Admin-Key header only when a key is set', () => {
    expect(adminHeaders()).toEqual({})
    setAdminKey('k')
    expect(adminHeaders()).toEqual({ 'X-Admin-Key': 'k' })
    clearAdminKey()
    expect(adminHeaders()).toEqual({})
  })

  it('ignores blank keys', () => {
    setAdminKey('   ')
    expect(getAdminKey()).toBe('')
  })

  it('never throws when storage is unavailable', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    expect(getAdminKey()).toBe('')
    expect(adminHeaders()).toEqual({})
    spy.mockRestore()
  })
})
