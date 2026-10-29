import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getReportTeams, getTeamReport } from './teamReport'
import * as client from './client'
import * as web from '@/webdata/client'
import { DATA_FLAG_KEY } from '@/localdata/source'

// The informe de equipo is the first page served from `web-data` (issue #639): with the local data source on it reads the sealed report published for
// the staff; with it off, or when the publication cannot answer, it asks the API as before. An access problem is NOT a reason to ask the API: the
// reader must be told to unlock (invitation), or the page would work for everyone through the server and the keys would mean nothing.
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const PUBLISHED = { team: 'DE WEB-DATA', mode: 'own' }
const FROM_API = { team: 'DE LA API', mode: 'own' }
const realFetch = globalThis.fetch
let apiCalls: string[]

beforeEach(() => {
  localStorage.clear()
  apiCalls = []
  globalThis.fetch = vi.fn(async (url: string) => { apiCalls.push(String(url)); return { ok: true, json: async () => FROM_API } }) as unknown as typeof fetch
})
afterEach(() => { globalThis.fetch = realFetch; vi.restoreAllMocks() })

const turnOn = () => localStorage.setItem(DATA_FLAG_KEY, 'local')

describe('getTeamReport with the local data source', () => {
  it('off: the API answers and web-data is not touched', async () => {
    const published = vi.spyOn(web, 'loadWebReport')
    expect(await getTeamReport(FEB, '101', 'own')).toEqual(FROM_API)
    expect(published).not.toHaveBeenCalled()
  })

  it('on: the published report answers and the API is not asked', async () => {
    turnOn()
    vi.spyOn(web, 'loadWebReport').mockResolvedValue(PUBLISHED as never)
    expect(await getTeamReport(FEB, '101', 'own')).toEqual(PUBLISHED)
    expect(apiCalls).toEqual([])
  })

  it('on, but the publication cannot answer: it falls back to the API', async () => {
    turnOn()
    vi.spyOn(web, 'loadWebReport').mockRejectedValue(new web.WebDataUnavailable('down'))
    expect(await getTeamReport(FEB, '101', 'own')).toEqual(FROM_API)
    expect(apiCalls.length).toBe(1)
  })

  it('on, and the reader has no key: the access error reaches the page, the API is NOT asked in its place', async () => {
    turnOn()
    vi.spyOn(web, 'loadWebReport').mockRejectedValue(new ScopedAccessError('sin acceso'))
    await expect(getTeamReport(FEB, '101', 'own')).rejects.toBeInstanceOf(ScopedAccessError)
    expect(apiCalls).toEqual([])
  })
})

describe('only the datasets that are on read web-data (issue #329)', () => {
  it('with `local:report-teams` the team list is local and the report still comes from the API', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:report-teams')
    const report = vi.spyOn(web, 'loadWebReport').mockResolvedValue(PUBLISHED as never)
    vi.spyOn(web, 'loadReportTeams').mockResolvedValue([{ id: '101', name: 'ALPHA' }])
    expect(await getReportTeams(FEB)).toEqual([{ id: '101', name: 'ALPHA' }])
    expect(await getTeamReport(FEB, '101', 'own')).toEqual(FROM_API)
    expect(report).not.toHaveBeenCalled()
  })
})

describe('getReportTeams with the local data source', () => {
  it('off: the teams of the API, as the page always had them', async () => {
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '10', name: 'Zamora' }] as never)
    expect(await getReportTeams(FEB)).toEqual([{ id: '10', name: 'Zamora' }])
  })

  it('on: the teams that have a published report; and the API ones if the publication cannot answer', async () => {
    turnOn()
    vi.spyOn(client, 'getLiveTeamNames').mockResolvedValue([{ id: '10', name: 'Zamora' }] as never)
    const published = vi.spyOn(web, 'loadReportTeams').mockResolvedValue([{ id: '101', name: 'ALPHA' }])
    expect(await getReportTeams(FEB)).toEqual([{ id: '101', name: 'ALPHA' }])
    published.mockRejectedValue(new web.WebDataUnavailable('down'))
    expect(await getReportTeams(FEB)).toEqual([{ id: '10', name: 'Zamora' }])
  })
})
