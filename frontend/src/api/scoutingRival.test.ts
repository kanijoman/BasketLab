import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

async function load(apiBase = '') {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE', apiBase)
  return import('./scoutingRival')
}

describe('rival scouting api (issue #299)', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset().mockResolvedValue({ ok: true, status: 202, json: async () => ({ job_id: 'j1' }), blob: async () => new Blob(['%PDF']) })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('starts the report of ANY team, with our team optional, honouring VITE_API_BASE', async () => {
    const api = await load('https://api.example.com')
    await expect(api.startScouting({ collection: 'FEB 25/26', team_id: '9', own_team_id: '1' })).resolves.toEqual({ job_id: 'j1' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.example.com/api/v1/scouting-rival')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ collection: 'FEB 25/26', team_id: '9', own_team_id: '1' })
  })

  it('polls the progress and reads the report of a job', async () => {
    fetchMock.mockResolvedValue({ ok: true, status: 200, json: async () => ({ status: 'running', current: 3, total: 10 }) })
    const api = await load()
    await expect(api.getScoutingProgress('a b')).resolves.toMatchObject({ current: 3, total: 10 })
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/scouting-rival/progress/a%20b')
    await api.getScoutingReport('j1')
    expect(fetchMock.mock.calls[1][0]).toBe('/api/v1/scouting-rival/report/j1')
  })

  it('makes the PDF in the browser from the report, without calling the server (issue #715)', async () => {
    const api = await load()
    fetchMock.mockClear()
    const report = {
      team: { id: '1', name: 'EQUIPO' }, own_team: { id: '2', name: 'MI CLUB' }, collection: 'FEB_X', sample_games: 3, games: [], low_sample: false, notices: [], record: { wins: 2, losses: 1, avg_for: 70, avg_against: 65, avg_margin: 5 },
      profile: [], keys: [], plan: { neutralize: [], exploit: [] }, players: [], lineups: [], origin: [], alerts: [], comparison: [],
    }
    const blob = await api.downloadScoutingPdf(report as never)
    expect(fetchMock).not.toHaveBeenCalled()
    expect(blob.type).toBe('application/pdf')
    expect(blob.size).toBeGreaterThan(1000)
  })

  it('turns the API detail into the error message', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 429, json: async () => ({ detail: 'Ya hay un informe en preparación; espera a que termine' }) })
    const api = await load()
    await expect(api.startScouting({ collection: 'c', team_id: '1' })).rejects.toThrow('Ya hay un informe en preparación')
  })
})
