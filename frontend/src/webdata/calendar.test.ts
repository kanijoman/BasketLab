import { beforeEach, describe, expect, it } from 'vitest'
import { loadWebCollectionInfos, loadWebRows, publishedSectionsOf, resetWebData, setDataBase, WebDataUnavailable } from './client'
import { loadWebCalendar } from './calendar'
import { FBCYL, FEB, readPublished, serveWebData, WEB_BASE, type WebDataHost } from '@/test/webDataHost'

// The calendar and the gender of `web-data` (issues #842, #843, #845), read from the REAL publication of the exporter (`tests/local_vectors/web_data`):
// the FEB calendar is the 12 games of the fixture league as results plus six still to play, the FBCYL one has the ESB rows with four still to play.
let host: WebDataHost
beforeEach(() => { localStorage.clear(); resetWebData(); setDataBase(WEB_BASE); host = serveWebData() })

describe('the calendar of a competition, opened in the browser', () => {
  it('opens the FEB calendar: results with a numeric score and the matches still to play with their kick-off', async () => {
    const calendar = await loadWebCalendar(FEB)
    expect(calendar).toMatchObject({ collection: FEB, league: 'feb', games: 18, ties_allowed: false })
    expect(calendar.matches.filter(m => m.kind === 'result')).toHaveLength(12)
    const pending = calendar.matches.filter(m => m.kind === 'scheduled')
    expect(pending).toHaveLength(6)
    expect(pending.every(m => m.score === null && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(m.start ?? ''))).toBe(true)
    expect(calendar.matches[0]).toMatchObject({ round: 1, kind: 'result', home: { id: '101', name: 'ALPHA' }, away: { id: '102', name: 'BRAVO' }, score: [125, 44] })
  })

  it('opens the FBCYL calendar: ids as texts, the kick-off of a played match too, and whether ties are allowed', async () => {
    const calendar = await loadWebCalendar(FBCYL)
    expect(calendar).toMatchObject({ league: 'fbcyl', games: 16, ties_allowed: false })
    expect(calendar.matches.filter(m => m.kind === 'result')).toHaveLength(12)
    expect(calendar.matches.every(m => typeof m.home.id === 'string' && typeof m.away.id === 'string' && !!m.start)).toBe(true)
  })

  it('a match is identified by the id its game has in the rows, so the results the rows already have can be told apart (FEB and FBCYL)', async () => {
    for (const collection of [FEB, FBCYL]) {
      const inRows = new Set((await loadWebRows(collection)).team_rows.map(r => String(r.match_id)))
      const results = (await loadWebCalendar(collection)).matches.filter(m => m.kind === 'result')
      expect(results.length).toBeGreaterThan(0)
      expect(results.every(m => inRows.has(m.match_id))).toBe(true)
    }
  })

  it('a competition with no calendar published is unavailable, not an access problem', async () => {
    const manifest = JSON.parse(readPublished('index.json'))
    manifest.calendar = manifest.calendar.filter((e: { collection: string }) => e.collection !== FEB)
    host.override['index.json'] = JSON.stringify(manifest)
    await expect(loadWebCalendar(FEB)).rejects.toBeInstanceOf(WebDataUnavailable)
    await expect(loadWebCalendar('NO_SUCH_COMPETITION')).rejects.toBeInstanceOf(WebDataUnavailable)
  })

  it('the calendar is one more section of the competition: the pages that need it can tell whether it is published', async () => {
    expect((await publishedSectionsOf(FEB)).has('calendar')).toBe(true)
    expect((await publishedSectionsOf('NO_SUCH_COMPETITION')).has('calendar')).toBe(false)
  })
})

describe('the gender of the competitions, from the manifest', () => {
  it('is in the list of published competitions when the exporter knew it', async () => {
    const infos = await loadWebCollectionInfos()
    expect(infos.find(i => i.collection === FEB)?.gender).toBe('F')
    expect(infos.find(i => i.collection === FBCYL)?.gender).toBe('F')
  })

  it('is absent when the publication does not say it (the caller uses the neutral values)', async () => {
    const manifest = JSON.parse(readPublished('index.json'))
    for (const row of manifest.rows) delete row.gender
    host.override['index.json'] = JSON.stringify(manifest)
    expect((await loadWebCollectionInfos()).every(i => i.gender === undefined)).toBe(true)
  })
})
