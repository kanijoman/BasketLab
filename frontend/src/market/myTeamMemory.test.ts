import { beforeEach, describe, expect, it } from 'vitest'
import { recallTeam, rememberTeam } from './myTeamMemory'

beforeEach(() => { localStorage.clear() })

describe('the team the staff chose (#882)', () => {
  it('is none at first, and is kept with its competition for the next visit', () => {
    expect(recallTeam()).toBeNull()
    rememberTeam({ comp: 'feb|lf2|2025', team: '101' })
    expect(recallTeam()).toEqual({ comp: 'feb|lf2|2025', team: '101' })
  })

  it('is forgotten with null, and a damaged or foreign value is nothing, never an error', () => {
    rememberTeam({ comp: 'a', team: 'b' })
    rememberTeam(null)
    expect(recallTeam()).toBeNull()
    for (const bad of ['{not json', '[]', '{"comp":1,"team":2}', '{"comp":"a"}', 'null']) {
      localStorage.setItem('talent-my-team', bad)
      expect(recallTeam()).toBeNull()
    }
  })

  it('does not fail when the storage is blocked', () => {
    const get = Storage.prototype.getItem
    Storage.prototype.getItem = () => { throw new Error('blocked') }
    try { expect(recallTeam()).toBeNull(); expect(() => rememberTeam({ comp: 'a', team: 'b' })).not.toThrow() } finally { Storage.prototype.getItem = get }
  })
})
