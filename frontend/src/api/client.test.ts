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

  it('prefixes requests with VITE_API_BASE', async () => {
    const api = await loadClient('https://api.example.com')
    await api.getLiveTeamNames('FEB 2025/26')
    expect(fetchMock.mock.calls[0][0]).toBe(
      'https://api.example.com/api/v1/teams/FEB%202025%2F26/teams',
    )
  })

  it('uses a relative /api/v1 URL when no base is set', async () => {
    const api = await loadClient('')
    await api.getLiveTeamNames('c1')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/teams/c1/teams')
  })

  it('surfaces the API error detail', async () => {
    fetchMock.mockResolvedValue({
      ok: false, status: 422, json: async () => ({ detail: 'bad input' }),
    } as Response)
    const api = await loadClient('')
    await expect(api.getLiveTeamNames('c1')).rejects.toThrow('bad input')
  })

  it('no longer exports endpoints that do not exist in the backend', async () => {
    const api = (await loadClient('')) as Record<string, unknown>
    expect(api.getPlayerRankings).toBeUndefined()
    expect(api.getPlayerRadar).toBeUndefined()
  })

  describe('admin key (#115)', () => {
    afterEach(() => sessionStorage.clear())

    it('sends X-Admin-Key when deleting a collection', async () => {
      sessionStorage.setItem('basketlab-admin-key', 'k')
      const api = await loadClient('')
      await api.deleteCollection('FEB_X')
      const [url, init] = fetchMock.mock.calls[0]
      expect(url).toBe('/api/v1/collections/FEB_X')
      expect(init.method).toBe('DELETE')
      expect(init.headers).toMatchObject({ 'X-Admin-Key': 'k' })
    })

    it('sends X-Admin-Key when starting a scrape', async () => {
      sessionStorage.setItem('basketlab-admin-key', 'k')
      const api = await loadClient('')
      await api.postScrapeStart({} as never)
      expect(fetchMock.mock.calls[0][1].headers).toMatchObject({ 'X-Admin-Key': 'k', 'Content-Type': 'application/json' })
    })

    it('sends no admin header without a key', async () => {
      const api = await loadClient('')
      await api.deleteCollection('FEB_X')
      expect(fetchMock.mock.calls[0][1].headers ?? {}).not.toHaveProperty('X-Admin-Key')
    })

    it('shows the server message when the key is missing or wrong', async () => {
      fetchMock.mockResolvedValue({
        ok: false, status: 401, json: async () => ({ detail: 'Clave de administración requerida o incorrecta' }),
      } as Response)
      const api = await loadClient('')
      await expect(api.deleteCollection('FEB_X')).rejects.toThrow('Clave de administración')
    })
  })
})
