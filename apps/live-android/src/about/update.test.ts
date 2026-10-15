import { describe, expect, it, vi } from 'vitest'
import { LATEST_URL, checkForUpdate, isNewer, parseLatest, type UpdateDeps } from './update'
import type { AppVersion } from './appInfo'

const INSTALLED: AppVersion = { name: '0.2.0', build: 40, builtAt: null, native: true }
const LATEST = {
  version: '0.3.0', versionCode: 52, apk: 'https://github.com/kanijoman/BasketLab/releases/download/live-android-latest/basketlab-live.apk',
  notes: 'Alineación indebida y feedback', built_at: '2026-10-16T07:30:00Z',
}

function memory() {
  const data = new Map<string, string>()
  return { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => { data.set(k, v) }, removeItem: (k: string) => { data.delete(k) } }
}

function deps(over: Partial<UpdateDeps> = {}): UpdateDeps {
  return { installed: INSTALLED, fetchJson: vi.fn().mockResolvedValue(LATEST), storage: memory(), now: () => 1_000_000, ...over }
}

describe('latest.json (issue #227)', () => {
  it('is published next to the fixed APK link of the latest release', () => {
    expect(LATEST_URL).toBe('https://github.com/kanijoman/BasketLab/releases/download/live-android-latest/latest.json')
  })

  it('is read when it has a version, a build number and an https link to the APK', () => {
    expect(parseLatest(LATEST)).toEqual({ version: '0.3.0', versionCode: 52, apk: LATEST.apk, notes: LATEST.notes, builtAt: LATEST.built_at })
    expect(parseLatest({ version: '0.3.0', versionCode: 52, apk: LATEST.apk })).toMatchObject({ notes: null, builtAt: null })
  })

  it.each([
    null, 'text', [], {},
    { ...LATEST, version: '' }, { ...LATEST, versionCode: 'x' }, { ...LATEST, versionCode: 0 }, { ...LATEST, versionCode: 1.5 },
    { ...LATEST, apk: 'http://insecure.example/app.apk' }, { ...LATEST, apk: 'javascript:alert(1)' }, { ...LATEST, apk: '' },
  ])('is ignored when it is not trustworthy: %j', bad => {
    expect(parseLatest(bad)).toBeNull()
  })
})

describe('is there a newer version?', () => {
  const latest = parseLatest(LATEST)!

  it('only when its build number is higher than the installed one', () => {
    expect(isNewer(latest, INSTALLED)).toBe(true)
    expect(isNewer(latest, { ...INSTALLED, build: 52 })).toBe(false)
    expect(isNewer(latest, { ...INSTALLED, build: 60 })).toBe(false)      // a rolled-back release never downgrades
  })

  it('never when the installed build is unknown (a browser or a development build)', () => {
    expect(isNewer(latest, { ...INSTALLED, build: null, native: false })).toBe(false)
  })
})

describe('checkForUpdate', () => {
  it('reports a newer version with its data', async () => {
    const r = await checkForUpdate(deps())
    expect(r).toMatchObject({ status: 'available', latest: { version: '0.3.0', apk: LATEST.apk } })
  })

  it('reports up to date when the installed build is the latest or newer', async () => {
    expect((await checkForUpdate(deps({ installed: { ...INSTALLED, build: 52 } }))).status).toBe('up_to_date')
  })

  it('only the app can update itself: in a browser there is nothing to check and no request is made', async () => {
    const fetchJson = vi.fn()
    const r = await checkForUpdate(deps({ installed: { ...INSTALLED, native: false }, fetchJson }))
    expect(r.status).toBe('unsupported')
    expect(fetchJson).not.toHaveBeenCalled()
  })

  it('without connection it simply does not say anything (unknown), it never throws', async () => {
    const r = await checkForUpdate(deps({ fetchJson: vi.fn().mockRejectedValue(new Error('offline')) }))
    expect(r.status).toBe('unknown')
  })

  it('an answer that is not a release description is unknown too', async () => {
    expect((await checkForUpdate(deps({ fetchJson: vi.fn().mockResolvedValue({ hello: 'world' }) }))).status).toBe('unknown')
  })

  it('remembers the last answer for a few minutes: a second automatic check right after makes no request', async () => {
    const d = deps()
    await checkForUpdate(d)
    const again = await checkForUpdate({ ...d, now: () => 1_000_000 + 5 * 60 * 1000 })
    expect(d.fetchJson).toHaveBeenCalledTimes(1)
    expect(again.status).toBe('available')
  })

  it('does not trust an answer for hours: a release published meanwhile must be noticed when the app opens (issue #335)', async () => {
    const d = deps()
    await checkForUpdate(d)
    await checkForUpdate({ ...d, now: () => 1_000_000 + 11 * 60 * 1000 })
    expect(d.fetchJson).toHaveBeenCalledTimes(2)
  })

  it('asks again after the cache expires, and always when the user presses the button', async () => {
    const d = deps()
    await checkForUpdate(d)
    await checkForUpdate({ ...d, now: () => 1_000_000 + 7 * 60 * 60 * 1000 })
    expect(d.fetchJson).toHaveBeenCalledTimes(2)
    await checkForUpdate({ ...d, force: true })
    expect(d.fetchJson).toHaveBeenCalledTimes(3)
  })

  it('a cached answer is judged against the version installed NOW (after an update the notice goes away)', async () => {
    const d = deps()
    await checkForUpdate(d)
    expect((await checkForUpdate({ ...d, installed: { ...INSTALLED, build: 52 } })).status).toBe('up_to_date')
  })

  it('works when the storage is blocked', async () => {
    const broken = { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('denied') }, removeItem: () => undefined }
    expect((await checkForUpdate(deps({ storage: broken }))).status).toBe('available')
  })
})
