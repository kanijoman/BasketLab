import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { DataUnavailable, fromSource } from './resolve'
import { DATA_FLAG_KEY } from './switch'
import { WebDataUnavailable } from '@/webdata/client'

// The ONE policy of the migration (issue #329): a dataset that is on reads the published files; if they cannot answer it reads the API as before;
// an access problem is not «cannot answer» (the reader must unlock: the API is not a way round the keys); any other error is an error.
const turnOn = (value = 'local') => localStorage.setItem(DATA_FLAG_KEY, value)
beforeEach(() => { localStorage.clear(); window.history.replaceState(null, '', '/') })

describe('fromSource', () => {
  it('off: the API answers and the local reader is never called', async () => {
    const local = vi.fn(async () => 'local')
    expect(await fromSource('team-stats', local, async () => 'api')).toBe('api')
    expect(local).not.toHaveBeenCalled()
  })

  it('on: the local answer is used and the API is not asked', async () => {
    turnOn()
    const api = vi.fn(async () => 'api')
    expect(await fromSource('team-stats', async () => 'local', api)).toBe('local')
    expect(api).not.toHaveBeenCalled()
  })

  it.each([
    ['null (nothing exported for it)', async () => null],
    ['DataUnavailable', async () => { throw new DataUnavailable('no') }],
    ['WebDataUnavailable (the publication is down or does not have it)', async () => { throw new WebDataUnavailable('no') }],
  ])('on, but the local side cannot answer (%s): the API answers', async (_name, local) => {
    turnOn()
    expect(await fromSource('team-stats', local as () => Promise<string | null>, async () => 'api')).toBe('api')
  })

  it('on, and the reader has no key: the access error reaches the caller and the API is not asked in its place', async () => {
    turnOn()
    const api = vi.fn(async () => 'api')
    await expect(fromSource('team-report', async () => { throw new ScopedAccessError('sin acceso') }, api)).rejects.toBeInstanceOf(ScopedAccessError)
    expect(api).not.toHaveBeenCalled()
  })

  it('on, and the local side fails for another reason: that error is not hidden by the API', async () => {
    turnOn()
    await expect(fromSource('team-stats', async () => { throw new TypeError('bug') }, async () => 'api')).rejects.toBeInstanceOf(TypeError)
  })

  it('only the datasets that are on read the local files: the others keep asking the API', async () => {
    turnOn('local:team-report')
    expect(await fromSource('team-report', async () => 'local', async () => 'api')).toBe('local')
    expect(await fromSource('team-stats', async () => 'local', async () => 'api')).toBe('api')
  })

  it('an API error is the caller\'s error, with the local side on or off', async () => {
    await expect(fromSource('team-stats', async () => 'local', async () => { throw new Error('HTTP 500') })).rejects.toThrow('HTTP 500')
    turnOn()
    await expect(fromSource('team-stats', async () => null, async () => { throw new Error('HTTP 500') })).rejects.toThrow('HTTP 500')
  })
})
