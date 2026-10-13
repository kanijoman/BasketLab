/**
 * Is there a newer APK? (issue #227). The release workflow publishes ``latest.json`` next to the fixed APK link of the
 * ``live-android-latest`` release: ``{version, versionCode, apk, notes, built_at}``. The app compares its build number
 * with that ``versionCode``. It never fails: offline, a bad answer or blocked storage just mean «unknown».
 * Android cannot install silently (only the Play Store can), so «update» opens the APK link and the system asks the
 * user to confirm.
 */
import type { AppVersion } from './appInfo'

export const LATEST_URL = 'https://github.com/kanijoman/BasketLab/releases/download/live-android-latest/latest.json'

const CACHE_KEY = 'basketlab-live-update'
const MAX_AGE_MS = 6 * 60 * 60 * 1000
const TIMEOUT_MS = 10_000

export interface LatestInfo {
  version: string
  versionCode: number
  apk: string
  notes: string | null
  builtAt: string | null
}

export type UpdateResult =
  | { status: 'available' | 'up_to_date'; latest: LatestInfo }
  | { status: 'unknown' }      // no connection or an answer that is not a release description
  | { status: 'unsupported' }  // not the Android app: nothing to update

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface UpdateDeps {
  installed: AppVersion | null
  fetchJson: (url: string) => Promise<unknown>
  storage?: StorageLike | null
  now?: () => number
  /** The user pressed the button: ignore the cache. */
  force?: boolean
}

/** A published release description, or null when it is not trustworthy (a bad link would be opened by the button). */
export function parseLatest(json: unknown): LatestInfo | null {
  if (!json || typeof json !== 'object' || Array.isArray(json)) return null
  const o = json as Record<string, unknown>
  const code = o.versionCode
  if (typeof o.version !== 'string' || !o.version || typeof code !== 'number' || !Number.isInteger(code) || code <= 0) return null
  if (typeof o.apk !== 'string' || !o.apk.startsWith('https://')) return null
  return {
    version: o.version, versionCode: code, apk: o.apk,
    notes: typeof o.notes === 'string' && o.notes ? o.notes : null,
    builtAt: typeof o.built_at === 'string' && o.built_at ? o.built_at : null,
  }
}

/** Only a higher build number is an update: a rolled-back release never downgrades, an unknown build never nags. */
export function isNewer(latest: LatestInfo, installed: AppVersion): boolean {
  return installed.build !== null && latest.versionCode > installed.build
}

function readCache(storage: StorageLike | null | undefined): { checkedAt: number; latest: unknown } | null {
  try {
    const parsed = JSON.parse(storage?.getItem(CACHE_KEY) ?? 'null')
    return parsed && typeof parsed.checkedAt === 'number' ? parsed : null
  } catch {
    return null
  }
}

function writeCache(storage: StorageLike | null | undefined, checkedAt: number, latest: unknown): void {
  try {
    storage?.setItem(CACHE_KEY, JSON.stringify({ checkedAt, latest }))
  } catch {
    /* blocked storage: it simply asks again next time */
  }
}

export async function checkForUpdate(d: UpdateDeps): Promise<UpdateResult> {
  if (!d.installed || !d.installed.native) return { status: 'unsupported' }
  const now = (d.now ?? Date.now)()
  const cached = readCache(d.storage)
  let raw: unknown
  if (!d.force && cached && now - cached.checkedAt < MAX_AGE_MS) {
    raw = cached.latest
  } else {
    try {
      raw = await d.fetchJson(LATEST_URL)
      if (parseLatest(raw)) writeCache(d.storage, now, raw)
    } catch {
      raw = cached?.latest  // offline: the last answer is still the best we know
    }
  }
  const latest = parseLatest(raw)
  if (!latest) return { status: 'unknown' }
  return { status: isNewer(latest, d.installed) ? 'available' : 'up_to_date', latest }
}

/** GET with a time limit; with CapacitorHttp this is the native HTTP of the app, which follows GitHub's redirect. */
export async function fetchJson(url: string): Promise<unknown> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  try {
    const response = await fetch(url, { cache: 'no-store', signal: controller.signal })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return await response.json()
  } finally {
    clearTimeout(timer)
  }
}
