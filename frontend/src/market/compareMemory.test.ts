import { beforeEach, describe, expect, it } from 'vitest'
import { compareHref, recallCompare, rememberCompare } from './compareMemory'

beforeEach(() => { sessionStorage.clear() })

describe('the comparison that is remembered between pages (#1007)', () => {
  it('is empty at first, keeps what was chosen and gives it back in the same order', () => {
    expect(recallCompare()).toEqual([])
    rememberCompare(['feb:2', 'feb:1'])
    expect(recallCompare()).toEqual(['feb:2', 'feb:1'])
    rememberCompare([])
    expect(recallCompare()).toEqual([])
  })

  it('builds the address of the comparator with the remembered list, and the plain one without it', () => {
    expect(compareHref()).toBe('/comparar')
    rememberCompare(['feb:1', 'fbcyl:u1'])
    expect(compareHref()).toBe('/comparar?j=feb%3A1%2Cfbcyl%3Au1')
  })

  it('never takes more than three, no repeats and no blanks, even from a damaged value', () => {
    sessionStorage.setItem('talent-compare', JSON.stringify(['a', 'a', '', 'b', 'c', 'd']))
    expect(recallCompare()).toEqual(['a', 'b', 'c'])
    sessionStorage.setItem('talent-compare', '{not json')
    expect(recallCompare()).toEqual([])
    sessionStorage.setItem('talent-compare', JSON.stringify({ x: 1 }))
    expect(recallCompare()).toEqual([])
  })

  it('does not fail when the storage is blocked', () => {
    const real = Storage.prototype.getItem
    Storage.prototype.getItem = () => { throw new Error('blocked') }
    try { expect(recallCompare()).toEqual([]); expect(() => rememberCompare(['a'])).not.toThrow() } finally { Storage.prototype.getItem = real }
  })
})
