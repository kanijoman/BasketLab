import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { getPublishedScouting, getScoutingScopes } from './scoutingRival'
import * as web from '@/webdata/client'
import { DATA_FLAG_KEY } from '@/datasource/switch'

// The full scouting of a rival is published by scope (issue #638). With the dataset `scouting` on the page reads it from web-data; with it off, or when the
// publication cannot say, it generates the report as always (a job on the server). No key is not «generate it on the server»: the reader must unlock.
const FEB = 'L_F_-2_2025_2026_Liga_Regular_B'
const REPORT = { scope: 'copa', team: { id: '101', name: 'ALPHA' } }

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('published scouting', () => {
  it('off: nothing published is read and the page keeps its job-based flow', async () => {
    const scopes = vi.spyOn(web, 'loadScoutingScopes')
    const scouting = vi.spyOn(web, 'loadWebScouting')
    expect(await getScoutingScopes(FEB, '101')).toEqual([])
    expect(await getPublishedScouting(FEB, '101', 'liga')).toBeNull()
    expect(scopes).not.toHaveBeenCalled()
    expect(scouting).not.toHaveBeenCalled()
  })

  it('on: the scopes and the report of a scope come from web-data', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(web, 'loadScoutingScopes').mockResolvedValue(['liga', 'copa', 'todo'])
    const scouting = vi.spyOn(web, 'loadWebScouting').mockResolvedValue(REPORT as never)
    expect(await getScoutingScopes(FEB, '101')).toEqual(['liga', 'copa', 'todo'])
    expect(await getPublishedScouting(FEB, '101', 'copa')).toEqual(REPORT)
    expect(scouting).toHaveBeenCalledWith(FEB, '101', 'copa')
  })

  it('only the dataset `scouting` reads it: with `local:team-report` the scouting is not published to this page', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local:team-report')
    const scouting = vi.spyOn(web, 'loadWebScouting')
    expect(await getPublishedScouting(FEB, '101', 'liga')).toBeNull()
    expect(scouting).not.toHaveBeenCalled()
  })

  it('on, but the publication cannot say: no scopes and no report (the page generates it)', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(web, 'loadScoutingScopes').mockRejectedValue(new web.WebDataUnavailable('down'))
    vi.spyOn(web, 'loadWebScouting').mockRejectedValue(new web.WebDataUnavailable('down'))
    expect(await getScoutingScopes(FEB, '101')).toEqual([])
    expect(await getPublishedScouting(FEB, '101', 'liga')).toBeNull()
  })

  it('on, and the reader has no key: the access error reaches the page', async () => {
    localStorage.setItem(DATA_FLAG_KEY, 'local')
    vi.spyOn(web, 'loadWebScouting').mockRejectedValue(new ScopedAccessError('sin acceso'))
    await expect(getPublishedScouting(FEB, '101', 'liga')).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
