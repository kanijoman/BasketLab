import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { loadPrefs, savePrefs, type Cut } from './storage'

// What the page remembers in the browser of whoever reads it, per competition: the own team and the cut lines. Per-viewer conveniences only: storage can be blocked, empty or damaged and the
// page must work without it.
beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('the preferences of a competition', () => {
  it('are empty when nothing was saved', () => {
    expect(loadPrefs('LIGA')).toEqual({ cuts: [] })
  })

  it('are what was saved, per competition', () => {
    savePrefs('LIGA', { team: '101' })
    savePrefs('OTRA', { team: '202' })
    expect(loadPrefs('LIGA').team).toBe('101')
    expect(loadPrefs('OTRA').team).toBe('202')
  })

  it('keep the cut lines and the team apart: saving one does not forget the other', () => {
    const cuts: Cut[] = [{ kind: 'top', n: 4 }, { kind: 'bottom', n: 2 }]
    savePrefs('LIGA', { team: '101' })
    savePrefs('LIGA', { cuts })
    expect(loadPrefs('LIGA')).toEqual({ team: '101', cuts })
  })

  it('forget the team when it is cleared', () => {
    savePrefs('LIGA', { team: '101' })
    savePrefs('LIGA', { team: undefined })
    expect(loadPrefs('LIGA').team).toBeUndefined()
  })
})

describe('what cannot be trusted', () => {
  it('damaged JSON is the defaults', () => {
    localStorage.setItem('basketlab.forecast.LIGA', '{not json')
    expect(loadPrefs('LIGA')).toEqual({ cuts: [] })
  })

  it('a value of another shape is the defaults, and a cut line that is not one is dropped', () => {
    localStorage.setItem('basketlab.forecast.LIGA', JSON.stringify(['a']))
    expect(loadPrefs('LIGA')).toEqual({ cuts: [] })
    localStorage.setItem('basketlab.forecast.LIGA', JSON.stringify({ team: 7, cuts: [{ kind: 'top', n: 4 }, { kind: 'middle', n: 3 }, { kind: 'top', n: -1 }, { kind: 'bottom', n: 2.5 }, null, { kind: 'bottom', n: 2 }] }))
    expect(loadPrefs('LIGA')).toEqual({ cuts: [{ kind: 'top', n: 4 }, { kind: 'bottom', n: 2 }] })
  })

  it('blocked storage is the defaults and saving is silent', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    expect(loadPrefs('LIGA')).toEqual({ cuts: [] })
    expect(() => savePrefs('LIGA', { team: '1' })).not.toThrow()
  })
})
