/**
 * Client of FEB's live API (issue #217): the match page hands out a JWT (hidden input) and BoxScore / KeyFacts /
 * ShotChart answer behind it. The same addresses and token rules as the Python scraper/recorder
 * (src/scraper/token_manager.py, src/live_prep/recorder.py).
 *
 * The match page sends no CORS headers, so on the tablet the requests go through Capacitor's native HTTP
 * (`defaultHttp`); tests and the web build inject their own `HttpGet`.
 */
import { Capacitor, CapacitorHttp } from '@capacitor/core'

export interface HttpResponse {
  status: number
  text: string
  /** Headers of the answer (any case): only ``age`` is read, to measure how stale the cache of FEB is (issue #411). */
  headers?: Record<string, string>
}

export type HttpGet = (url: string, headers?: Record<string, string>) => Promise<HttpResponse>

export type Endpoint = 'boxscore' | 'keyfacts' | 'shotchart'

export const FEB_PAGE = (code: string) => `https://baloncestoenvivo.feb.es/partido/${code}`
const API = 'https://intrafeb.feb.es/LiveStats.API/api/v1'
export const FEB_ENDPOINT: Record<Endpoint, (code: string) => string> = {
  boxscore: code => `${API}/BoxScore/${code}`,
  keyfacts: code => `${API}/KeyFacts/${code}`,
  shotchart: code => `${API}/ShotChart/${code}`,
}

const BROWSER_HEADERS = { Accept: 'application/json, text/html;q=0.9, */*;q=0.8', 'Accept-Language': 'es-ES,es;q=0.9' }

/** Native HTTP on the tablet (no CORS), plain fetch elsewhere. */
export const defaultHttp: HttpGet = async (url, headers = {}) => {
  const all = { ...BROWSER_HEADERS, ...headers }
  if (Capacitor.isNativePlatform()) {
    const response = await CapacitorHttp.get({ url, headers: all, responseType: 'text' })
    return {
      status: response.status, text: typeof response.data === 'string' ? response.data : JSON.stringify(response.data),
      headers: response.headers,
    }
  }
  const response = await fetch(url, { headers: all })
  // (a browser only lets a cross-origin page read the headers FEB exposes: ``age`` is then missing and the meter says so)
  return { status: response.status, text: await response.text(), headers: response.headers ? Object.fromEntries(response.headers.entries()) : undefined }
}

const HIDDEN_INPUT = /<input\b[^>]*\btype=["']?hidden["']?[^>]*>/gi
const BEARER = /Bearer\s+(eyJ[A-Za-z0-9\-_.]+)/

/** The JWT of a match page: hidden input first (what FEB uses), then a Bearer token written in a script. */
export function extractToken(html: string): string | null {
  for (const input of html.match(HIDDEN_INPUT) ?? []) {
    const value = input.match(/\bvalue=["']?([^"'\s>]+)/i)?.[1]
    if (value && value.startsWith('eyJhbGci')) return value
  }
  return html.match(BEARER)?.[1] ?? null
}

export interface FebResult {
  status: number
  /** Parsed body of a 200; null otherwise (404 = not started or a gap in the feed). */
  json: unknown | null
  /** The token had expired and was renewed for this request. */
  renewed?: boolean
  /** Seconds the answer had been in the cache of FEB (header ``age``), when it said. */
  age?: number
}

/** The ``age`` header, whatever the case of its name; undefined when it is missing or not a number. */
function ageOf(headers?: Record<string, string>): number | undefined {
  const entry = Object.entries(headers ?? {}).find(([name]) => name.toLowerCase() === 'age')
  const age = entry ? Number(entry[1]) : NaN
  return Number.isFinite(age) ? age : undefined
}

export class FebClient {
  private token: string | null = null

  constructor(private readonly http: HttpGet) {}

  private async fetchToken(code: string): Promise<string> {
    const page = await this.http(FEB_PAGE(code))
    const token = page.status === 200 ? extractToken(page.text) : null
    if (!token) throw new Error(`No se pudo obtener el token de FEB para el partido ${code} (HTTP ${page.status})`)
    return token
  }

  async fetch(code: string, endpoint: Endpoint): Promise<FebResult> {
    this.token ??= await this.fetchToken(code)
    const url = FEB_ENDPOINT[endpoint](code)
    let response = await this.http(url, { Authorization: `Bearer ${this.token}` })
    let renewed = false
    if (response.status === 401) {  // expired: renew once and retry (the real JWT lasted > 2 h)
      this.token = await this.fetchToken(code)
      renewed = true
      response = await this.http(url, { Authorization: `Bearer ${this.token}` })
    }
    const age = ageOf(response.headers)
    const extra = { ...(renewed ? { renewed } : {}), ...(age !== undefined ? { age } : {}) }
    if (response.status !== 200) return { status: response.status, json: null, ...extra }
    try {
      return { status: 200, json: JSON.parse(response.text), ...extra }
    } catch {
      throw new Error(`FEB devolvió algo que no es JSON (${endpoint})`)
    }
  }
}
