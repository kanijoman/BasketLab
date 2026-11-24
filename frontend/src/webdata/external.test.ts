import { beforeEach, describe, expect, it } from 'vitest'
import { loadSourceFreshness, loadWebCollectionInfos, loadWebCollections, loadWebMatches, loadWebRows, resetWebData, setDataBase, setExtDataBase, sourceOf } from './client'
import { EXT_BASE, FBCYL, FEB, FIBA, NCAA, serveBoth, WEB_BASE, type TwoHosts } from '@/test/webDataHost'

// The external sources (ACB, FIBA, NCAA; #884, PR C) are published in `web-data-ext`, apart from `web-data` so that a failure of one never stops the other. The web reads both: the two publications are the
// REAL ones of the exporter (`tests/local_vectors/web_data` and `web_data_ext`, the second with FIBA fresh and NCAA failed on its last run). Which one holds a competition is read from the name of its collection
// (the prefix of its source), so no request is made to find out; and the second one being down never takes the first with it.
let hosts: TwoHosts
beforeEach(() => { resetWebData(); setDataBase(WEB_BASE); setExtDataBase(EXT_BASE); hosts = serveBoth() })

describe('which publication holds a competition', () => {
  it.each([[FIBA, 'fiba'], [NCAA, 'ncaa'], ['ACB_Liga_Endesa_2026_', 'acb'], ['EUROLEAGUE_EuroLeague_2025_', 'euroleague'], ['EUROLEAGUES_2025', null], [FEB, null], [FBCYL, null], ['NCAAB_2026', null], ['', null]])('%s is %s', (name, source) => {
    expect(sourceOf(name)).toBe(source)
  })
})

describe('the list of competitions of both publications', () => {
  it('has the competitions of FEB and FBCYL and the external ones, each with its league and its names', async () => {
    const infos = await loadWebCollectionInfos()
    expect(infos.map(i => [i.collection, i.league])).toEqual([[FBCYL, 'fbcyl'], [FEB, 'feb'], [FIBA, 'fiba'], [NCAA, 'ncaa']])
    expect(infos.find(i => i.collection === NCAA)).toMatchObject({ league: 'ncaa', gender: 'M', category: 'senior', competition_label: 'NCAA D1', group_label: 'SEC' })
    expect((await loadWebCollections()).sort()).toEqual([FBCYL, FEB, FIBA, NCAA].sort())
  })

  it('still lists FEB when the external publication is down, does not exist yet or is of another schema', async () => {
    hosts.ext.override['index.json'] = null
    expect((await loadWebCollectionInfos()).map(i => i.collection)).toEqual([FBCYL, FEB])
    resetWebData()
    hosts.ext.override['index.json'] = JSON.stringify({ schema: 999, v: 2, rows: [] })
    expect((await loadWebCollectionInfos()).map(i => i.collection)).toEqual([FBCYL, FEB])
    resetWebData()
    hosts.ext.override['index.json'] = 'not json'
    expect((await loadWebCollectionInfos()).map(i => i.collection)).toEqual([FBCYL, FEB])
  })

  it('is the list of FEB alone while the external publication has no competition', async () => {
    hosts.ext.override['index.json'] = JSON.stringify({ schema: 1, v: 2, sources: [], rows: [] })
    expect((await loadWebCollectionInfos()).map(i => i.collection)).toEqual([FBCYL, FEB])
  })
})

describe('the files of a competition come from the publication that holds it', () => {
  it('opens the rows of an external competition from web-data-ext and asks web-data for nothing but its own manifest', async () => {
    const rows = await loadWebRows(FIBA)
    expect(rows.league).toBe('fiba')
    expect(hosts.ext.requested.some(f => f.startsWith('rows/'))).toBe(true)
    expect(hosts.web.requested.some(f => f.startsWith('rows/'))).toBe(false)
  })

  it('never asks the external publication for a competition of FEB', async () => {
    await loadWebRows(FEB)
    expect(hosts.ext.requested).toEqual([])
  })

  it('opens the sections of an external competition too (the matches, the first of the files besides the rows)', async () => {
    expect((await loadWebMatches(NCAA)).matches.length).toBeGreaterThan(0)
    expect(hosts.ext.requested.some(f => f.startsWith('matches/'))).toBe(true)
  })

  it('says there is no answer, as for any competition not published, when the external publication is down', async () => {
    hosts.ext.override['index.json'] = null
    await expect(loadWebRows(FIBA)).rejects.toThrow(/no están disponibles|no tiene datos/i)
    expect((await loadWebRows(FEB)).collection).toBe(FEB)                      // and FEB goes on
  })
})

describe('how fresh each external source is', () => {
  it('says when each source last worked and that NCAA failed on its last run', async () => {
    expect(await loadSourceFreshness()).toEqual([
      expect.objectContaining({ source: 'fiba', state: 'ok', ok: true, last_ok: '2026-11-18T07:00:00Z', games: 13, unreliable: 12, published: 1 }),
      expect.objectContaining({ source: 'ncaa', state: 'failed', ok: false, last_ok: '2026-11-17T07:00:00Z', finished: '2026-11-18T07:00:00Z' }),
    ])
  })

  it('is empty, never an error, when the external publication is down or says nothing', async () => {
    hosts.ext.override['index.json'] = null
    expect(await loadSourceFreshness()).toEqual([])
    resetWebData()
    hosts.ext.override['index.json'] = JSON.stringify({ schema: 1, v: 2, rows: [] })              // a manifest without the field
    expect(await loadSourceFreshness()).toEqual([])
  })
})
