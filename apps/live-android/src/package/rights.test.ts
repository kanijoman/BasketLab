// @vitest-environment node
// The rights of the device (issue #410): invitations kept to open the scopes of the packages, and how an invitation is read.
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { activeRights, addRight, loadRights, parseInvite, removeRight, scopeKeys } from './rights'

const repoRoot = path.resolve(import.meta.dirname, '../../../..')
const demo = JSON.parse(fs.readFileSync(path.join(repoRoot, 'tests/live_vectors/demo_scoped.json'), 'utf8'))
const { token, link } = demo.invitations['club:1008631']

function memory(): Storage {
  const data = new Map<string, string>()
  return { getItem: k => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: k => void data.delete(k), clear: () => data.clear(), key: () => null, length: 0 } as Storage
}

describe('parseInvite', () => {
  it('reads the token and the link that the generator prints (what Python wrote)', () => {
    expect(parseInvite(token)).toMatchObject({ scope: 'club:1008631', expires: '2027-06-30' })
    expect(parseInvite(link)).toEqual(parseInvite(token))
    expect(parseInvite(`  ${link}\n`).scope).toBe('club:1008631')           // as pasted from a chat
  })

  it('refuses what is not an invitation, with a message that says what to do', () => {
    for (const bad of ['', 'hola', 'bl1.', 'bl1.@@@', 'bl2.eyJ9']) expect(() => parseInvite(bad)).toThrow(/invitación/i)
  })
})

describe('the rights of the device', () => {
  it('are kept, replaced by scope and removed', () => {
    const storage = memory()
    expect(loadRights(storage)).toEqual([])
    addRight(parseInvite(token), storage)
    addRight(parseInvite(token), storage)
    expect(loadRights(storage).map(r => r.scope)).toEqual(['club:1008631'])
    removeRight('club:1008631', storage)
    expect(loadRights(storage)).toEqual([])
  })

  it('survive a storage that is broken or holds rubbish', () => {
    const storage = memory()
    storage.setItem('basketlab-live-rights', '{no json')
    expect(loadRights(storage)).toEqual([])
    expect(() => addRight(parseInvite(token), { ...memory(), setItem: () => { throw new Error('full') } } as Storage)).not.toThrow()
  })

  it('an expired right is not used (a convention of the app: the real cut is the rotation of the scope)', () => {
    const rights = [{ scope: 'club:1', key: 'AAAA', expires: '2026-06-30' }, { scope: 'club:2', key: 'AAAA', expires: '2027-06-30' }, { scope: 'club:3', key: 'AAAA', expires: null }]
    expect(activeRights(rights, new Date('2026-10-20')).map(r => r.scope)).toEqual(['club:2', 'club:3'])
  })
})

describe('scopeKeys', () => {
  it('are the published open key and the rights that are still valid, as bytes', () => {
    const keys = scopeKeys({ open_key: demo.open_key }, [parseInvite(token)], new Date('2026-10-20'))
    expect(keys.map(k => k.scope)).toEqual(['abierto', 'club:1008631'])
    expect(keys.every(k => k.key.length === 32)).toBe(true)
    expect(scopeKeys({}, [], new Date()).length).toBe(0)
  })
})
