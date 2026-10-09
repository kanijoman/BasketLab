import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

async function load(apiBase = '') {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE', apiBase)
  return import('./livePackage')
}

describe('live package api', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset().mockResolvedValue({ ok: true, status: 202, json: async () => ({ job_id: 'j1' }), blob: async () => new Blob(['x']) })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  const req = { collection: 'FEB 25/26', team_id: '1', rival_id: '2', passphrase: 'clave-segura-1' }

  it('posts the request as JSON to /live/package honouring VITE_API_BASE', async () => {
    const api = await load('https://api.example.com')
    await expect(api.startLivePackage(req)).resolves.toEqual({ job_id: 'j1' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.example.com/api/v1/live/package')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual(req)
    expect(init.headers['Content-Type']).toBe('application/json')
  })

  it('polls the progress of a job', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'running', current: 3, total: 10 }) })
    const api = await load()
    await expect(api.getLivePackageProgress('a b')).resolves.toMatchObject({ current: 3, total: 10 })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/live/package/progress/a%20b')
  })

  it('downloads the package as a blob', async () => {
    const api = await load()
    const blob = await api.downloadLivePackage('j1')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/live/package/download/j1')
    expect(blob).toBeInstanceOf(Blob)
  })

  it('surfaces the server message (busy, validation, unsupported collection)', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 429, json: async () => ({ detail: 'Ya hay un paquete en preparación' }) })
    const api = await load()
    await expect(api.startLivePackage(req)).rejects.toThrow('Ya hay un paquete en preparación')
    await expect(api.downloadLivePackage('j1')).rejects.toThrow('Ya hay un paquete en preparación')
  })

  it('formats FastAPI validation errors (list of details)', async () => {
    fetchMock.mockResolvedValue({
      ok: false, status: 422,
      json: async () => ({ detail: [{ msg: 'String should have at least 8 characters', loc: ['body', 'passphrase'] }] }),
    })
    const api = await load()
    await expect(api.startLivePackage(req)).rejects.toThrow(/at least 8 characters/)
  })

  it('lists the upcoming matches of a team', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ matches: [{ code: '1' }], calendar_url: 'u', warning: null }) })
    const api = await load()
    await expect(api.getLiveMatches('FEB 25/26', '7', 3)).resolves.toMatchObject({ matches: [{ code: '1' }] })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/live/matches/FEB%2025%2F26?team_id=7&limit=3')
  })

  it('sends the chosen match code with the package request', async () => {
    const api = await load()
    await api.startLivePackage({ ...req, match_code: '2524465' })
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).match_code).toBe('2524465')
  })
})
