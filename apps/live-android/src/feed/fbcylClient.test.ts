// @vitest-environment node
import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { describe, expect, it, vi } from 'vitest'
import { FbcylClient, calendarUrl, decodeCalendar, movesUrl, statsUrl, streamUrl } from './fbcylClient'
import type { HttpGet } from './febClient'

// Issue #446 (PR 3). The calendar of the group A-1 as the ESB API answers it (Base64 of UTF-8 JSON, the rounds with their matches), built from the 156 REAL rows of
// `tests/fixtures/fbcyl_calendar_7298.json.gz`.
const rows: Record<string, unknown>[] = JSON.parse(zlib.gunzipSync(fs.readFileSync(path.resolve(import.meta.dirname, '../../../../tests/fixtures/fbcyl_calendar_7298.json.gz'))).toString('utf8')).rows

function answer(source: Record<string, unknown>[] = rows): string {
  const rounds: Record<string, { date: unknown; matches: Record<string, unknown> }> = {}
  for (const r of source) (rounds[String(r.round)] ??= { date: r.round_date, matches: {} }).matches[String(r.idMatch)] = r
  return Buffer.from(JSON.stringify({ result: 'OK', messageData: { rounds } }), 'utf8').toString('base64')
}
const http = (status: number, text: string): HttpGet => vi.fn(async () => ({ status, text }))

describe('decodeCalendar', () => {
  it('reads every row of the real calendar, with its round, the state and the keys of the match', () => {
    const decoded = decodeCalendar(answer())
    expect(decoded).toHaveLength(156)
    const played = decoded.find(r => r.idMatch === '148988')!
    expect(played).toMatchObject({ round: '1', state: '1', adGameId: '23212', universallyid: '6ac127a0b0e0bc33f6a951bb', isLive: false })
    const pending = decoded.find(r => r.state === '0')!
    expect(pending.adGameId).toBeNull()                                           // a pending match has no adGameId yet
    expect(pending.universallyid).toBeNull()
  })

  it('reads accents as UTF-8 (the answer is Base64 of bytes, not of text)', () => {
    const decoded = decodeCalendar(answer([{ ...rows[0], idMatch: '1', nameLocalTeam: 'ÑOÑO CAÑÓN' }]))
    expect(decoded).toHaveLength(1)
  })

  it('an answer that is not a good calendar gives no rows instead of throwing', () => {
    expect(decodeCalendar('not base64 !!')).toEqual([])
    expect(decodeCalendar(Buffer.from('{"result":"KO"}').toString('base64'))).toEqual([])
    expect(decodeCalendar('')).toEqual([])
  })
})

describe('FbcylClient', () => {
  it('asks the calendar of the group and says when it cannot be read', async () => {
    const ok = vi.fn(async () => ({ status: 200, text: answer() }))
    expect(await new FbcylClient(ok).calendar('7298')).toHaveLength(156)
    expect(ok).toHaveBeenCalledWith(calendarUrl('7298'))
    await expect(new FbcylClient(http(503, '')).calendar('7298')).rejects.toThrow(/503/)
    await expect(new FbcylClient(http(200, Buffer.from('{"result":"OK","messageData":{"rounds":{}}}').toString('base64'))).calendar('7298')).rejects.toThrow(/vacío/)
  })

  it('gives the body of the stream, or none when the service does not answer well', async () => {
    expect(await new FbcylClient(http(200, '{"period":1}')).stream('23958')).toEqual({ status: 200, text: '{"period":1}' })
    expect(await new FbcylClient(http(404, 'nope')).stream('23958')).toEqual({ status: 404, text: null })
  })

  it('gives the definitive moves and stats only when msstats has both', async () => {
    const calls: string[] = []
    const both: HttpGet = async url => { calls.push(url); return { status: 200, text: url.includes('Moves') ? '[1]' : '{"s":1}' } }
    expect(await new FbcylClient(both).final('abc')).toEqual({ moves: '[1]', stats: '{"s":1}' })
    expect(calls.sort()).toEqual([movesUrl('abc'), statsUrl('abc')].sort())
    const half: HttpGet = async url => ({ status: url.includes('Moves') ? 200 : 404, text: '[]' })
    expect(await new FbcylClient(half).final('abc')).toBeNull()
  })

  it('the addresses are the ones of the recorder of the project', () => {
    expect(streamUrl('23958')).toBe('https://streaming.optimalwayconsulting.com/fbcyl/streaming/match-id/23958')
    expect(calendarUrl('7298')).toMatch(/getAllGamesByGrupWithMatchRecords\/7298\/0$/)
    expect(statsUrl('abc')).toBe('https://msstats.optimalwayconsulting.com/v1/fbcyl/getJsonWithMatchStats/abc?currentSeason=true')
  })
})
