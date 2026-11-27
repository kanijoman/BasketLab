import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

function okResponse(body: unknown = []) {
  return { ok: true, status: 200, json: async () => body } as Response
}

async function loadClient(apiBase?: string) {
  vi.resetModules()
  if (apiBase !== undefined) vi.stubEnv('VITE_API_BASE', apiBase)
  return import('./client')
}

describe('api client', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset().mockResolvedValue(okResponse())
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('no longer exports endpoints that do not exist in the backend', async () => {
    const api = (await loadClient('')) as Record<string, unknown>
    expect(api.getPlayerRankings).toBeUndefined()
    expect(api.getPlayerRadar).toBeUndefined()
  })

  describe('lineup period filter', () => {
    it('offers the full season, the last game and the day ranges', async () => {
      const api = await loadClient('')
      expect(api.LINEUP_PERIODS.map(p => p.label)).toEqual([
        'Temporada completa', 'Último partido', 'Últimos 7 días', 'Últimos 15 días', 'Últimos 30 días', 'Últimos 60 días',
      ])
      expect(api.LINEUP_PERIODS.find(p => p.label === 'Último partido')?.value).toBe(api.LAST_GAME)
    })
  })
})
