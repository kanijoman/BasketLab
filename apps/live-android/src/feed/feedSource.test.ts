import { describe, expect, it } from 'vitest'
import { fbcylMatchId, isConnectable, isFbcylCode, shownCode, sourceOf } from './feedSource'

// Issue #446 (PR 3): FEB codes are digits, the ones of FBCYL `fbcyl-<idMatch>`; the league decides the feed and the words of the screen, nothing else.
describe('the league of a match code', () => {
  it.each([
    ['2524475', 'FEB', '2524475', null],
    ['fbcyl-149388', 'FBCYL', '149388', '149388'],
    ['  ', 'FEB', '  ', null],
    ['fbcyl-', 'FEB', 'fbcyl-', null],
    ['FBCYL-149388', 'FEB', 'FBCYL-149388', null],
    ['fbcyl-14a', 'FEB', 'fbcyl-14a', null],
  ])('%s is %s, shown as %s', (code, league, shown, id) => {
    expect(sourceOf(code)).toBe(league)
    expect(shownCode(code)).toBe(shown)
    expect(fbcylMatchId(code)).toBe(id)
    expect(isFbcylCode(code)).toBe(league === 'FBCYL')
  })

  it('only digits or a FBCYL code can be connected', () => {
    expect(['2524475', 'fbcyl-149388'].every(isConnectable)).toBe(true)
    expect(['', 'abc', 'fbcyl-', '12 34', 'fbcyl-1-2'].some(isConnectable)).toBe(false)
  })
})
