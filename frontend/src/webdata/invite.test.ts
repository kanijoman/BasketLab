import { beforeEach, describe, expect, it } from 'vitest'
import { loadRights } from '@live-package/rights'
import { consumeInviteFromUrl } from './invite'

// An invitation arrives as a link: `<page>#invite=bl1.<token>` (the live app's `basketlab-live://invite#<token>` made for a web page). Opening it adds the
// right and takes the key out of the address bar, so that it is not left in the history, in a screenshot or in what the reader copies and shares.
const token = (scope: string) => `bl1.${btoa(JSON.stringify({ s: scope, k: btoa(String.fromCharCode(...new Uint8Array(32).fill(7))), e: null })).replace(/=+$/, '')}`

beforeEach(() => { localStorage.clear(); window.history.replaceState(null, '', '/') })

describe('consumeInviteFromUrl', () => {
  it('adds the right of a valid invitation and clears the address', () => {
    window.history.replaceState(null, '', `/informe?x=1#invite=${token('club:101')}`)
    expect(consumeInviteFromUrl()?.scope).toBe('club:101')
    expect(loadRights().map(r => r.scope)).toEqual(['club:101'])
    expect(window.location.hash).toBe('')
    expect(window.location.pathname + window.location.search).toBe('/informe?x=1')          // the rest of the address stays
  })

  it('ignores an address without an invitation and leaves other hashes alone', () => {
    window.history.replaceState(null, '', '/x#seccion')
    expect(consumeInviteFromUrl()).toBeNull()
    expect(window.location.hash).toBe('#seccion')
    expect(loadRights()).toEqual([])
  })

  it('an invitation that does not work adds nothing, does not throw and is not left in the address', () => {
    window.history.replaceState(null, '', '/x#invite=bl1.esto-no-es-una-clave')
    expect(consumeInviteFromUrl()).toBeNull()
    expect(loadRights()).toEqual([])
    expect(window.location.hash).toBe('')
  })

  it('a newer invitation to the same scope replaces the old one', () => {
    window.history.replaceState(null, '', `/x#invite=${token('club:101')}`)
    consumeInviteFromUrl()
    window.history.replaceState(null, '', `/x#invite=${token('club:101')}`)
    consumeInviteFromUrl()
    expect(loadRights().length).toBe(1)
  })
})
