import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadManifest, loadMatch, type DemoMatch } from './demo'

const MATCH: DemoMatch = {
  code: '2524470', title: 'Recoletas Zamora – Mipelletymas B.F. Leon', date: '2026-10-10T17:00',
  home: { id: '1008898', name: 'RECOLETAS ZAMORA' }, away: { id: '1008631', name: 'MIPELLETYMAS B.F. LEON' },
  recording: '2524470.recording.json', package: '2524470.package.json',
}

afterEach(() => vi.unstubAllGlobals())

const reply = (body: unknown, ok = true) => ({
  ok, status: ok ? 200 : 404, json: async () => body, text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
})

describe('loadManifest', () => {
  it('reads the list of demo matches, newest first as generated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply([MATCH])))
    expect(await loadManifest()).toEqual([MATCH])
  })

  it('a missing manifest or a manifest of the wrong shape is an empty list (the app uses the sample game)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply('Not Found', false)))
    expect(await loadManifest()).toEqual([])
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({ v: 1, packages: [] })))
    expect(await loadManifest()).toEqual([])
  })

  it('a network error is an empty list, not a crash', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    expect(await loadManifest()).toEqual([])
  })
})

describe('loadMatch', () => {
  it('fetches the package and the recording of a match', async () => {
    const fetchMock = vi.fn(async (url: string) => reply(url.endsWith('package.json') ? 'PKG' : 'REC'))
    vi.stubGlobal('fetch', fetchMock)
    expect(await loadMatch(MATCH)).toEqual({ package: 'PKG', recording: 'REC' })
    const urls = fetchMock.mock.calls.map(c => c[0])
    expect(urls).toEqual(expect.arrayContaining([
      expect.stringContaining('/demo/2524470.package.json'), expect.stringContaining('/demo/2524470.recording.json'),
    ]))
  })

  it('fails with a readable error when a file is missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply('nope', false)))
    await expect(loadMatch(MATCH)).rejects.toThrow(/2524470/)
  })
})
