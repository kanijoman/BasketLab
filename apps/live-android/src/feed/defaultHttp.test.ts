import { afterEach, describe, expect, it, vi } from 'vitest'

const native = vi.hoisted(() => ({ isNative: false, get: vi.fn() }))
vi.mock('@capacitor/core', () => ({
  Capacitor: { isNativePlatform: () => native.isNative },
  CapacitorHttp: { get: native.get },
}))

import { defaultHttp } from './febClient'

afterEach(() => { vi.unstubAllGlobals(); native.get.mockReset(); native.isNative = false })

describe('defaultHttp', () => {
  it('on the tablet goes through the native HTTP (the match page sends no CORS headers)', async () => {
    native.isNative = true
    native.get.mockResolvedValue({ status: 200, data: '<html>página</html>' })
    const response = await defaultHttp('https://baloncestoenvivo.feb.es/partido/1', { Authorization: 'Bearer x' })
    expect(native.get).toHaveBeenCalledWith(expect.objectContaining({
      url: 'https://baloncestoenvivo.feb.es/partido/1', responseType: 'text',
      headers: expect.objectContaining({ Authorization: 'Bearer x' }),
    }))
    expect(response).toEqual({ status: 200, text: '<html>página</html>' })
  })

  it('native data that arrives already parsed is turned back into text', async () => {
    native.isNative = true
    native.get.mockResolvedValue({ status: 200, data: { HEADER: { status: '2' } } })
    expect((await defaultHttp('https://x/api')).text).toBe('{"HEADER":{"status":"2"}}')
  })

  it('outside the tablet uses fetch', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ status: 404, text: async () => '{}' })
    vi.stubGlobal('fetch', fetchMock)
    expect(await defaultHttp('https://x/api')).toEqual({ status: 404, text: '{}' })
    expect(fetchMock).toHaveBeenCalledWith('https://x/api', expect.objectContaining({ headers: expect.any(Object) }))
    expect(native.get).not.toHaveBeenCalled()
  })
})
