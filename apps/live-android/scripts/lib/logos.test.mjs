// @vitest-environment node
// Team crests are downloaded during the build (not committed: club crests in a public repo): the ids come from the
// FEB calendar of the competitions of config/atlas_refresh.json (issue #230).
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadLogos, fbcylLogosFromCalendar, febLogoUrl, teamIdsFromCalendar } from './logos.mjs'

const calendar = fs.readFileSync(path.resolve(import.meta.dirname, '../../../../tests/fixtures/feb_calendar_snippet.html'), 'utf8')
const tmp = []
const outDir = () => { const d = fs.mkdtempSync(path.join(os.tmpdir(), 'logos-')); tmp.push(d); return d }
afterEach(() => { for (const d of tmp.splice(0)) fs.rmSync(d, { recursive: true, force: true }) })

const png = (n = 200) => new Uint8Array(n).fill(7)
const ok = (bytes = png()) => ({ ok: true, status: 200, arrayBuffer: async () => bytes.buffer, headers: { get: () => 'image/png' } })

describe('teamIdsFromCalendar', () => {
  it('collects every team id of the calendar once', () => {
    const ids = teamIdsFromCalendar(calendar)
    expect(ids.length).toBeGreaterThan(2)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.every(id => /^\d+$/.test(id))).toBe(true)
  })

  it('finds the id in the team links', () => {
    expect(teamIdsFromCalendar('<a href="Equipo.aspx?i=1008631&c=1">León</a><a href="/Equipo.aspx?i=1008898">Zamora</a>')).toEqual(['1008631', '1008898'])
  })

  it('a page without teams gives no ids', () => {
    expect(teamIdsFromCalendar('<html></html>')).toEqual([])
  })
})

describe('downloadLogos', () => {
  it('saves one PNG per team named after its id and reports what happened', async () => {
    const dir = outDir()
    const fetchFn = vi.fn(async () => ok())
    const result = await downloadLogos(['1', '2'], dir, fetchFn)
    expect(fs.readdirSync(dir).sort()).toEqual(['1.png', '2.png'])
    expect(fetchFn).toHaveBeenCalledWith(febLogoUrl('1'), expect.anything())
    expect(result).toEqual({ saved: 2, skipped: 0, failed: [] })
  })

  it('keeps going when one logo fails and says which (the app falls back to initials)', async () => {
    const dir = outDir()
    const fetchFn = vi.fn(async url => (url.includes('i=2&') ? { ok: false, status: 404 } : ok()))
    const result = await downloadLogos(['1', '2', '3'], dir, fetchFn)
    expect(result.saved).toBe(2)
    expect(result.failed).toEqual([{ id: '2', reason: 'HTTP 404' }])
  })

  it('a network error is a failure of that logo, not of the build', async () => {
    const result = await downloadLogos(['1'], outDir(), async () => { throw new Error('offline') })
    expect(result.failed).toEqual([{ id: '1', reason: 'offline' }])
  })

  it('does not download again what is already there', async () => {
    const dir = outDir()
    fs.writeFileSync(path.join(dir, '1.png'), png())
    const fetchFn = vi.fn(async () => ok())
    const result = await downloadLogos(['1', '2'], dir, fetchFn)
    expect(fetchFn).toHaveBeenCalledTimes(1)
    expect(result).toMatchObject({ saved: 1, skipped: 1 })
  })

  it('refuses a body that is not a small image (a login page, an error page)', async () => {
    const dir = outDir()
    const huge = { ok: true, status: 200, arrayBuffer: async () => png(1_200_000).buffer, headers: { get: () => 'image/png' } }
    const html = { ok: true, status: 200, arrayBuffer: async () => png().buffer, headers: { get: () => 'text/html' } }
    const result = await downloadLogos(['1', '2'], dir, async url => (url.includes('i=1&') ? huge : html))
    expect(fs.readdirSync(dir)).toEqual([])
    expect(result.failed.map(f => f.reason)).toEqual(['too large', 'not an image'])
  })

  it('shrinks the crest before saving it: FEB serves 500x500 PNGs of up to 260 KB, the app needs ~96 px', async () => {
    const dir = outDir()
    const resize = vi.fn(async () => new Uint8Array([1, 2, 3]))
    const result = await downloadLogos(['1'], dir, async () => ok(png(250_000)), { resize })
    expect(resize).toHaveBeenCalledTimes(1)
    expect([...fs.readFileSync(path.join(dir, '1.png'))]).toEqual([1, 2, 3])
    expect(result.saved).toBe(1)
  })

  it('a crest that cannot be shrunk is a failure of that logo (initials are shown), not of the build', async () => {
    const dir = outDir()
    const result = await downloadLogos(['1'], dir, async () => ok(), { resize: async () => { throw new Error('corrupt image') } })
    expect(fs.readdirSync(dir)).toEqual([])
    expect(result.failed).toEqual([{ id: '1', reason: 'corrupt image' }])
  })

  it('the real resizer (sharp) turns a big PNG into a small square one', async () => {
    const { default: sharp } = await import('sharp')
    const { resizeLogo } = await import('./logos.mjs')
    const big = await sharp({ create: { width: 500, height: 500, channels: 4, background: { r: 200, g: 30, b: 30, alpha: 1 } } }).png().toBuffer()
    const small = await resizeLogo(new Uint8Array(big))
    const meta = await sharp(Buffer.from(small)).metadata()
    expect([meta.width, meta.height, meta.format]).toEqual([96, 96, 'png'])
    expect(small.byteLength).toBeLessThan(big.byteLength)
  })
})


describe('FBCYL crests (issue #514)', () => {
  const calendarJson = { messageData: { rounds: { 1: { matches: {
    10: { idLocalTeam: '40285', logoLocal: 'https://cdn.example/a.png', idVisitorTeam: '40286', logoVisitant: 'https://cdn.example/b.jpg' },
    11: { idLocalTeam: '40286', logoLocal: 'https://cdn.example/b.jpg', idVisitorTeam: '40287', logoVisitant: null },
  } } } } }

  it('takes the crest of every team from the calendar of its group, once, with the id the stored games use (idLocalTeam = teamIdExtern)', () => {
    expect(fbcylLogosFromCalendar(calendarJson)).toEqual([
      { id: '40285', url: 'https://cdn.example/a.png' }, { id: '40286', url: 'https://cdn.example/b.jpg' }])
  })

  it('a calendar without data or without logos gives nothing', () => {
    expect(fbcylLogosFromCalendar({})).toEqual([])
    expect(fbcylLogosFromCalendar({ messageData: { rounds: {} } })).toEqual([])
  })

  it('downloads from the url of the team, not from FEB, and names the file after the id', async () => {
    const dir = outDir()
    const fetchFn = vi.fn(async () => ok())
    const result = await downloadLogos([{ id: '40285', url: 'https://cdn.example/a.png' }], dir, fetchFn)
    expect(fs.readdirSync(dir)).toEqual(['40285.png'])
    expect(fetchFn).toHaveBeenCalledWith('https://cdn.example/a.png', expect.anything())
    expect(result.saved).toBe(1)
  })
})
