// The link of an invitation opens the app (issue #410): `basketlab-live://invite#<token>` is kept as a right and the Partidos tab is told.
import fs from 'node:fs'
import path from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const plugin = vi.hoisted(() => {
  const state = { handler: null as null | ((event: { url: string }) => void), launch: undefined as string | undefined }
  return {
    state,
    addListener: vi.fn(async (_name: string, cb: (event: { url: string }) => void) => {
      state.handler = cb
      return { remove: vi.fn(async () => { state.handler = null }) }
    }),
    getLaunchUrl: vi.fn(async () => ({ url: state.launch })),
  }
})
vi.mock('@capacitor/app', () => ({ App: { addListener: plugin.addListener, getLaunchUrl: plugin.getLaunchUrl } }))

import { acceptInviteUrl, listenInviteLinks } from './inviteLink'
import { RIGHTS_EVENT, loadRights } from './rights'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const demo = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_scoped.json'), 'utf8'))
const link: string = demo.invitations['club:1008631'].link

beforeEach(() => {
  vi.clearAllMocks()
  plugin.state.handler = null
  plugin.state.launch = undefined
  localStorage.clear()
})

describe('acceptInviteUrl', () => {
  it('keeps the right of an invitation link and says which scope it opens', () => {
    expect(acceptInviteUrl(link)).toEqual({ ok: true, scope: 'club:1008631' })
    expect(loadRights().map(r => r.scope)).toEqual(['club:1008631'])
  })

  it('ignores a link that is not an invitation and refuses one that is broken, keeping nothing', () => {
    expect(acceptInviteUrl('https://example.com/')).toBeNull()
    expect(acceptInviteUrl('basketlab-live://invite#bl1.@@@')).toMatchObject({ ok: false, message: expect.stringMatching(/invitación/i) })
    expect(loadRights()).toEqual([])
  })
})

describe('listenInviteLinks', () => {
  it('reports the links that open the app while it runs and tells the lists to read the rights again', async () => {
    const results: unknown[] = []
    const seen = vi.fn()
    window.addEventListener(RIGHTS_EVENT, seen)
    const stop = listenInviteLinks(r => results.push(r))
    await vi.waitFor(() => expect(plugin.state.handler).not.toBeNull())
    plugin.state.handler!({ url: link })
    expect(results).toEqual([{ ok: true, scope: 'club:1008631' }])
    expect(seen).toHaveBeenCalledTimes(1)
    plugin.state.handler!({ url: 'otra-cosa://x' })
    expect(results.length).toBe(1)
    stop()
    window.removeEventListener(RIGHTS_EVENT, seen)
  })

  it('also handles the link that launched the app', async () => {
    plugin.state.launch = link
    const results: unknown[] = []
    listenInviteLinks(r => results.push(r))
    await vi.waitFor(() => expect(results).toEqual([{ ok: true, scope: 'club:1008631' }]))
  })

  it('on the web, where the plugin fails, it does nothing and does not break', async () => {
    plugin.addListener.mockRejectedValueOnce(new Error('not implemented'))
    plugin.getLaunchUrl.mockRejectedValueOnce(new Error('not implemented'))
    expect(() => listenInviteLinks(vi.fn())()).not.toThrow()
  })
})
