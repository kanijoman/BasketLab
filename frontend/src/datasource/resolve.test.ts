import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { DataNotAvailable, DataUnavailable, fromSource } from './resolve'
import { DATA_FLAG_KEY } from './switch'
import { WebDataUnavailable } from '@/webdata/client'

// The ONE policy of the migration (issues #329, #334): a dataset that is local reads the published files and NOTHING asks a server in its place: if they cannot answer, the reader gets
// a clear error (or the neutral value the caller says). The API is only read when it is asked for on purpose (`?data=api`, the mode of the development and of the e2e).
// An access problem is not «cannot answer» either (the reader must unlock); any other error is an error.
const turnOn = (value = 'local') => localStorage.setItem(DATA_FLAG_KEY, value)
beforeEach(() => { localStorage.clear(); localStorage.setItem('basketlab.data', 'api'); window.history.replaceState(null, '', '/') })

describe('fromSource', () => {
  it('the API asked for on purpose: the API answers and the local reader is never called', async () => {
    const local = vi.fn(async () => 'local')
    expect(await fromSource('team-stats', local, async () => 'api')).toBe('api')
    expect(local).not.toHaveBeenCalled()
  })

  it('local: the local answer is used and the API is not asked', async () => {
    turnOn()
    const api = vi.fn(async () => 'api')
    expect(await fromSource('team-stats', async () => 'local', api)).toBe('local')
    expect(api).not.toHaveBeenCalled()
  })

  it('local, but nothing answers (null): a clear error, and the API is NOT asked in its place', async () => {
    turnOn()
    const api = vi.fn(async () => 'api')
    const error = await fromSource('team-stats', async () => null, api).catch(e => e)
    expect(error).toBeInstanceOf(DataNotAvailable)
    expect((error as DataNotAvailable).dataset).toBe('team-stats')
    expect((error as Error).message).toMatch(/no están disponibles|no se pueden/i)
    expect(api).not.toHaveBeenCalled()
  })

  it.each([
    ['DataUnavailable', () => new DataUnavailable('Datos no disponibles.')],
    ['WebDataUnavailable (the publication is down or does not have it)', () => new WebDataUnavailable('No se pudo conectar con los datos publicados.')],
  ])('local, but the published files fail (%s): that error, which already says why, reaches the caller; the API is not asked', async (_name, make) => {
    turnOn()
    const api = vi.fn(async () => 'api')
    const failure = make()
    await expect(fromSource('team-stats', async () => { throw failure }, api)).rejects.toBe(failure)
    expect(api).not.toHaveBeenCalled()
  })

  it('local, nothing answers, and the caller has a neutral value: that value (not an error), for null and for DataUnavailable', async () => {
    turnOn()
    expect(await fromSource<string[]>('scouting', async () => null, async () => ['api'], () => [])).toEqual([])
    expect(await fromSource<string[]>('scouting', async () => { throw new WebDataUnavailable('no') }, async () => ['api'], () => [])).toEqual([])
  })

  it('local, and the reader has no key: the access error reaches the caller, not the neutral value, not the API', async () => {
    turnOn()
    const api = vi.fn(async () => 'api')
    await expect(fromSource('team-report', async () => { throw new ScopedAccessError('sin acceso') }, api, () => 'neutral')).rejects.toBeInstanceOf(ScopedAccessError)
    expect(api).not.toHaveBeenCalled()
  })

  it('local, and the local side fails for another reason: that error is not hidden', async () => {
    turnOn()
    await expect(fromSource('team-stats', async () => { throw new TypeError('bug') }, async () => 'api', () => 'neutral')).rejects.toBeInstanceOf(TypeError)
  })

  it('only the datasets that are local read the files: the others ask the API, because it was asked for', async () => {
    turnOn('local:team-report')
    expect(await fromSource('team-report', async () => 'local', async () => 'api')).toBe('local')
    expect(await fromSource('team-stats', async () => 'local', async () => 'api')).toBe('api')
  })

  it('an API error (asked for on purpose) is the caller\'s error', async () => {
    await expect(fromSource('team-stats', async () => 'local', async () => { throw new Error('HTTP 500') })).rejects.toThrow('HTTP 500')
  })
})
