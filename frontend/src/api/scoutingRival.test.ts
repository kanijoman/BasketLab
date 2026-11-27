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

})
