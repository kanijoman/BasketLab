import { describe, expect, it } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { DataNotAvailable, DataUnavailable, fromSource } from './resolve'
import { WebDataUnavailable } from '@/webdata/client'

// The ONE policy (issues #329, #334, #1199): a dataset reads the published files and NOTHING asks a server in its place (the API was retired): if they cannot answer, the reader gets
// a clear error (or the neutral value the caller says). An access problem is not «cannot answer» either (the reader must unlock); any other error is an error.
describe('fromSource', () => {
  it('the local answer is used', async () => {
    expect(await fromSource('team-stats', async () => 'local')).toBe('local')
  })

  it('nothing answers (null): a clear error that names the dataset', async () => {
    const error = await fromSource('team-stats', async () => null).catch(e => e)
    expect(error).toBeInstanceOf(DataNotAvailable)
    expect((error as DataNotAvailable).dataset).toBe('team-stats')
    expect((error as Error).message).toMatch(/no están disponibles|no se pueden/i)
  })

  it.each([
    ['DataUnavailable', () => new DataUnavailable('Datos no disponibles.')],
    ['WebDataUnavailable (the publication is down or does not have it)', () => new WebDataUnavailable('No se pudo conectar con los datos publicados.')],
  ])('the published files fail (%s): that error, which already says why, reaches the caller', async (_name, make) => {
    const failure = make()
    await expect(fromSource('team-stats', async () => { throw failure })).rejects.toBe(failure)
  })

  it('nothing answers and the caller has a neutral value: that value (not an error), for null and for DataUnavailable', async () => {
    expect(await fromSource<string[]>('scouting', async () => null, () => [])).toEqual([])
    expect(await fromSource<string[]>('scouting', async () => { throw new WebDataUnavailable('no') }, () => [])).toEqual([])
  })

  it('the reader has no key: the access error reaches the caller, not the neutral value', async () => {
    await expect(fromSource('team-report', async () => { throw new ScopedAccessError('sin acceso') }, () => 'neutral')).rejects.toBeInstanceOf(ScopedAccessError)
  })

  it('the local side fails for another reason: that error is not hidden', async () => {
    await expect(fromSource('team-stats', async () => { throw new TypeError('bug') }, () => 'neutral')).rejects.toBeInstanceOf(TypeError)
  })
})
