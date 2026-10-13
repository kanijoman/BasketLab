/**
 * Test helper (not shipped logic): a fake FEB that serves a packed real recording with its real timeline —
 * a TypeScript twin of src/live_core/recorded_feed.py + fake_feb.py. The match page carries the JWT in a hidden
 * input; BoxScore / KeyFacts / ShotChart answer 401 without the right token and 404 where the real feed did.
 */
import type { HttpGet, HttpResponse } from './febClient'

interface Entry<T> { f: number; r?: number; fix?: [number, T][]; l?: T; s?: T }
export interface Pack {
  v: number
  match: string
  base: { HEADER: Record<string, unknown>; BOXSCORE: unknown; PLAYBYPLAY: Record<string, unknown>; SHOTCHART: Record<string, unknown> }
  lines: Entry<Record<string, unknown>>[]
  shots: Entry<Record<string, unknown>>[]
  frames: { t: number; h: { status: string; statusText: string; quarter: number; time: string; pts: Record<string, number> } }[]
  gaps: Record<string, [number, number][]>
}

type Doc = Record<string, unknown>

export class FakeFeb {
  /** Seconds of the recording "now" (the test moves it); a fake clock in place of real time. */
  at = 0
  requests: { url: string; token: string | null }[] = []
  /** Tokens accepted by the API: the page hands out `tokens[0]`; call `expire()` to make it hand out the next one. */
  private tokens: string[]
  private issued = 0

  constructor(private readonly pack: Pack, tokens = ['eyJhbGciFAKE.one.token', 'eyJhbGciFAKE.two.token']) {
    this.tokens = tokens
  }

  get duration(): number {
    const ends = [this.pack.frames[this.pack.frames.length - 1].t]
    for (const spans of Object.values(this.pack.gaps)) for (const [, end] of spans) ends.push(end)
    return Math.max(...ends)
  }

  /** The JWT of the current page: after `expire()` the old one answers 401. */
  expire() { this.issued = Math.min(this.issued + 1, this.tokens.length - 1) }

  private inGap(endpoint: string, t: number) {
    return (this.pack.gaps[endpoint] ?? []).some(([a, b]) => a <= t && t < b)
  }

  private documentAt(t: number): Doc | null {
    let frame = -1
    for (let i = 0; i < this.pack.frames.length && this.pack.frames[i].t <= t; i++) frame = i
    if (frame < 0) return null
    const visible = <T,>(e: Entry<T>) => e.f <= frame && (e.r === undefined || frame < e.r)
    const status = this.pack.frames[frame].h
    const header = JSON.parse(JSON.stringify(this.pack.base.HEADER)) as { TEAM?: { id: string; pts: string }[] }
    Object.assign(header, { status: status.status, statusText: status.statusText, quarter: status.quarter, time: status.time })
    for (const team of header.TEAM ?? []) if (String(team.id) in status.pts) team.pts = String(status.pts[String(team.id)])
    const lines = this.pack.lines.filter(visible).map(e => {
      let line = e.l!
      for (const [at, version] of e.fix ?? []) if (at <= frame) line = version
      return line
    })
    const shots = this.pack.shots.filter(visible).map(e => e.s!)
    return {
      HEADER: header,
      BOXSCORE: this.pack.base.BOXSCORE,
      PLAYBYPLAY: { ...this.pack.base.PLAYBYPLAY, LINES: lines },
      SHOTCHART: { ...this.pack.base.SHOTCHART, SHOTS: shots },
    }
  }

  get: HttpGet = async (url, headers = {}): Promise<HttpResponse> => {
    const auth = headers.Authorization ?? null
    this.requests.push({ url, token: auth ? auth.replace('Bearer ', '') : null })
    const page = url.match(/\/partido\/(\d+)$/)
    if (page) {
      return { status: 200, text: `<html><body><input type="hidden" id="token" value="${this.tokens[this.issued]}" /></body></html>` }
    }
    const api = url.match(/\/LiveStats\.API\/api\/v1\/(BoxScore|KeyFacts|ShotChart)\/(\d+)$/)
    if (!api) return { status: 404, text: '{}' }
    if (auth !== `Bearer ${this.tokens[this.issued]}`) return { status: 401, text: '' }
    const endpoint = api[1].toLowerCase()
    const doc = this.documentAt(this.at)
    if (!doc || this.inGap(endpoint, this.at)) return { status: 404, text: '{}' }
    const body = endpoint === 'boxscore'
      ? { HEADER: doc.HEADER, BOXSCORE: doc.BOXSCORE }
      : endpoint === 'keyfacts' ? { PLAYBYPLAY: doc.PLAYBYPLAY } : { SHOTCHART: doc.SHOTCHART }
    return { status: 200, text: JSON.stringify(body) }
  }
}
