import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

async function load(apiBase = '') {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE', apiBase)
  return import('./pbpExtended')
}

describe('pbp extended api', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset().mockResolvedValue({ ok: true, status: 200, json: async () => [{ team_name: 'A' }] })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it.each([
    ['getPointsByOrigin', 'points-by-origin'],
    ['getByPeriod', 'by-period'],
    ['getSituations', 'situations'],
    ['getTimeoutEffects', 'timeouts'],
  ] as const)('%s asks /possessions/<collection>/%s, honouring VITE_API_BASE', async (fn, path) => {
    const api = await load('https://api.example.com')
    const rows = await api[fn]('LF Challenge 26/27')

    expect(fetchMock.mock.calls[0][0]).toBe(`https://api.example.com/api/v1/possessions/LF%20Challenge%2026%2F27/${path}`)
    expect(rows).toEqual([{ team_name: 'A' }])
  })

  it('surfaces the API error detail', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 503, json: async () => ({ detail: 'Base de datos no disponible' }) })
    const api = await load()

    await expect(api.getSituations('c1')).rejects.toThrow('Base de datos no disponible')
  })

  it('falls back to the HTTP status when the error has no detail', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500, json: async () => { throw new Error('no json') } })
    const api = await load()

    await expect(api.getByPeriod('c1')).rejects.toThrow('HTTP 500')
  })
})
