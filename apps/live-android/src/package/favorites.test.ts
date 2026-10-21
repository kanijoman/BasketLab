import { describe, expect, it } from 'vitest'
import { addFavorite, isFavorite, loadFavorites, removeFavorite, toggleFavorite, type Favorite } from './favorites'

function memory(initial?: string): Storage {
  const data = new Map<string, string>(initial === undefined ? [] : [['basketlab-live-favorites', initial]])
  return {
    getItem: k => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: k => void data.delete(k), clear: () => data.clear(),
    key: () => null, get length() { return data.size },
  }
}

const leonesa: Favorite = { teamId: '1008857', name: 'CULTURAL Y DEPORTIVA LEONESA' }

describe('favorite teams of the device (issue #440)', () => {
  it('starts empty and keeps what was added', () => {
    const s = memory()
    expect(loadFavorites(s)).toEqual([])
    addFavorite(leonesa, s)
    expect(loadFavorites(s)).toEqual([leonesa])
  })

  it('a team is kept once: adding it again replaces it (same id)', () => {
    const s = memory()
    addFavorite(leonesa, s)
    addFavorite({ ...leonesa, name: 'LEONESA' }, s)
    expect(loadFavorites(s)).toEqual([{ teamId: '1008857', name: 'LEONESA' }])
  })

  it('removes a team by id', () => {
    const s = memory()
    addFavorite(leonesa, s)
    addFavorite({ teamId: '2', name: 'OTRO' }, s)
    removeFavorite('1008857', s)
    expect(loadFavorites(s)).toEqual([{ teamId: '2', name: 'OTRO' }])
  })

  it('toggle adds the team the first time and removes it the second, and says what it did', () => {
    const s = memory()
    expect(toggleFavorite(leonesa, s)).toBe(true)
    expect(loadFavorites(s)).toEqual([leonesa])
    expect(toggleFavorite(leonesa, s)).toBe(false)
    expect(loadFavorites(s)).toEqual([])
  })

  it('a team is recognised by its id, or by its name when the id changed (ids change every season)', () => {
    const favs = [leonesa]
    expect(isFavorite(favs, '1008857', 'LO QUE SEA')).toBe(true)
    expect(isFavorite(favs, '9999999', 'Cultural y Deportiva Leonesa')).toBe(true)     // another season: new id, same name
    expect(isFavorite(favs, '9999999', '  CULTURAL  Y DEPORTIVA   LEÓNESA ')).toBe(true) // case, accents and spaces do not matter
    expect(isFavorite(favs, '5', 'LLÍRIA')).toBe(false)
  })

  it('toggling a team recognised by name removes the saved one', () => {
    const s = memory()
    addFavorite(leonesa, s)
    expect(toggleFavorite({ teamId: '9999999', name: 'Cultural y Deportiva Leonesa' }, s)).toBe(false)
    expect(loadFavorites(s)).toEqual([])
  })

  it('ignores corrupted or foreign contents', () => {
    expect(loadFavorites(memory('no json'))).toEqual([])
    expect(loadFavorites(memory('{"a":1}'))).toEqual([])
    expect(loadFavorites(memory(JSON.stringify([{ teamId: '1', name: 'A' }, { name: 'sin id' }, 7, null])))).toEqual([{ teamId: '1', name: 'A' }])
  })

  it('works without storage (private mode): it just does not remember', () => {
    const broken = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') } } as unknown as Storage
    expect(loadFavorites(broken)).toEqual([])
    expect(() => addFavorite(leonesa, broken)).not.toThrow()
  })
})
