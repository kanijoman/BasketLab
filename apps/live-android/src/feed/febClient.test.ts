import { describe, expect, it, vi } from 'vitest'
import { FebClient, extractToken, type HttpGet } from './febClient'

const JWT = 'eyJhbGciOiJIUzI1NiJ9.payload.signature'
const page = (html: string) => ({ status: 200, text: html })

describe('extractToken', () => {
  it('reads the JWT of the hidden input of the match page', () => {
    expect(extractToken(`<html><input type="hidden" id="token" value="${JWT}" /></html>`)).toBe(JWT)
  })

  it('ignores hidden inputs that are not a JWT', () => {
    const html = `<input type="hidden" value="__VIEWSTATE123" /><input type='hidden' value='${JWT}'>`
    expect(extractToken(html)).toBe(JWT)
  })

  it('falls back to a Bearer token written in a script', () => {
    expect(extractToken(`<script>var h = "Authorization: Bearer ${JWT}";</script>`)).toBe(JWT)
  })

  it('is null when the page has no token', () => {
    expect(extractToken('<html><body>nada</body></html>')).toBeNull()
  })
})

function client(script: Record<string, { status: number; text: string }[]>) {
  const calls: { url: string; auth?: string }[] = []
  const http: HttpGet = vi.fn(async (url, headers) => {
    calls.push({ url, auth: headers?.Authorization })
    const queue = Object.entries(script).find(([key]) => url.includes(key))?.[1]
    if (!queue) return { status: 404, text: '{}' }
    return queue.length > 1 ? queue.shift()! : queue[0]
  })
  return { feb: new FebClient(http), calls }
}

describe('FebClient', () => {
  it('gets the token from the match page once and sends it as a Bearer token', async () => {
    const { feb, calls } = client({ '/partido/': [page(`<input type="hidden" value="${JWT}">`)], BoxScore: [{ status: 200, text: '{"HEADER":{"status":"2"}}' }] })
    expect((await feb.fetch('777', 'boxscore')).json).toEqual({ HEADER: { status: '2' } })
    await feb.fetch('777', 'boxscore')
    expect(calls.filter(c => c.url.includes('/partido/'))).toHaveLength(1)
    expect(calls.find(c => c.url.includes('BoxScore'))!.auth).toBe(`Bearer ${JWT}`)
  })

  it('uses the right FEB addresses', async () => {
    const { feb, calls } = client({ '/partido/': [page(`<input type="hidden" value="${JWT}">`)] })
    await feb.fetch('2524470', 'keyfacts')
    await feb.fetch('2524470', 'shotchart')
    const urls = calls.map(c => c.url)
    expect(urls).toContain('https://baloncestoenvivo.feb.es/partido/2524470')
    expect(urls).toContain('https://intrafeb.feb.es/LiveStats.API/api/v1/KeyFacts/2524470')
    expect(urls).toContain('https://intrafeb.feb.es/LiveStats.API/api/v1/ShotChart/2524470')
  })

  it('renews an expired token once on a 401 and retries', async () => {
    const second = 'eyJhbGciSECOND.token.value'
    const { feb, calls } = client({
      '/partido/': [page(`<input type="hidden" value="${JWT}">`), page(`<input type="hidden" value="${second}">`)],
      BoxScore: [{ status: 401, text: '' }, { status: 200, text: '{"ok":true}' }],
    })
    const result = await feb.fetch('777', 'boxscore')
    expect(result).toMatchObject({ status: 200, json: { ok: true }, renewed: true })
    expect(calls.filter(c => c.url.includes('BoxScore')).map(c => c.auth)).toEqual([`Bearer ${JWT}`, `Bearer ${second}`])
  })

  it('gives up after one renewal: a second 401 is reported, not looped on', async () => {
    const { feb } = client({ '/partido/': [page(`<input type="hidden" value="${JWT}">`)], BoxScore: [{ status: 401, text: '' }] })
    expect((await feb.fetch('777', 'boxscore')).status).toBe(401)
  })

  it('a 404 (not started / a gap) has no body to parse', async () => {
    const { feb } = client({ '/partido/': [page(`<input type="hidden" value="${JWT}">`)], BoxScore: [{ status: 404, text: '{}' }] })
    expect(await feb.fetch('777', 'boxscore')).toMatchObject({ status: 404, json: null })
  })

  it('fails with a clear message when the page has no token', async () => {
    const { feb } = client({ '/partido/': [page('<html></html>')] })
    await expect(feb.fetch('777', 'boxscore')).rejects.toThrow(/token/i)
  })

  it('a body that is not JSON is an error for that poll, not a crash', async () => {
    const { feb } = client({ '/partido/': [page(`<input type="hidden" value="${JWT}">`)], BoxScore: [{ status: 200, text: '<html>mantenimiento</html>' }] })
    await expect(feb.fetch('777', 'boxscore')).rejects.toThrow(/JSON/i)
  })

  // #411: the age of the cache of FEB answers is a fact of the delay of the feed
  it('reads the age of the answer from the headers of FEB, whatever the case of the name', async () => {
    const http: HttpGet = vi.fn(async (url: string) => (url.includes('/partido/')
      ? page(`<input type="hidden" value="${JWT}">`)
      : { status: 200, text: '{}', headers: { Age: '11', 'Cache-Control': 'public,max-age=15' } }))
    const feb = new FebClient(http)
    expect((await feb.fetch('777', 'boxscore')).age).toBe(11)
  })

  it('has no age when the headers do not have it (older clients, a browser that hides it)', async () => {
    const { feb } = client({ '/partido/': [page(`<input type="hidden" value="${JWT}">`)], BoxScore: [{ status: 200, text: '{}' }] })
    expect((await feb.fetch('777', 'boxscore')).age).toBeUndefined()
  })
})
