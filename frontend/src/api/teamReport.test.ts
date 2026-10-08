import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

async function load(apiBase = '') {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE', apiBase)
  return import('./teamReport')
}

describe('team report api', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset().mockResolvedValue({ ok: true, status: 200, json: async () => ({ team: 'A' }), blob: async () => new Blob(['x']) })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
  })

  it('requests the JSON report with team and mode, honouring VITE_API_BASE', async () => {
    const api = await load('https://api.example.com')
    await api.getTeamReport('FEB 25/26', '7', 'rival')
    expect(fetchMock.mock.calls[0][0]).toBe(
      'https://api.example.com/api/v1/reports/team-report/FEB%2025%2F26?team_id=7&mode=rival',
    )
  })

  it('downloads the PDF from the /pdf endpoint', async () => {
    const api = await load()
    const blob = await api.downloadTeamReportPdf('c1', '7', 'own')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/reports/team-report/c1/pdf?team_id=7&mode=own')
    expect(blob).toBeInstanceOf(Blob)
  })

  it('surfaces the API error detail', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404, statusText: 'Not Found', json: async () => ({ detail: 'Equipo no encontrado: 7' }) })
    const api = await load()
    await expect(api.getTeamReport('c1', '7', 'own')).rejects.toThrow('Equipo no encontrado: 7')
    await expect(api.downloadTeamReportPdf('c1', '7', 'own')).rejects.toThrow('Equipo no encontrado: 7')
  })
})
