import { beforeEach, describe, expect, it } from 'vitest'
import { DATASETS, DATA_FLAG_KEY, dataSourceOf, localDatasets, localDataEnabled, apiDatasets } from './switch'

// The switch of the local-first migration (issues #329, #334): which datasets the web reads from the published files and which from the API. Since #334 the default is
// LOCAL for every dataset (the API is the fallback when the files cannot answer, and goes away with Render): `?data=api` forces the API, `?data=local` goes back to the
// default, `?data=local:team-report,team-stats` turns on only those. The choice is remembered in the browser.
const at = (search: string) => window.history.replaceState(null, '', `/x${search}`)

beforeEach(() => { localStorage.clear(); at('') })

describe('which datasets read the local files', () => {
  it('all of them by default: nothing is stored and nothing is asked', () => {
    expect(localDataEnabled()).toBe(true)
    expect(localDatasets().sort()).toEqual([...DATASETS].sort())
    expect(DATASETS.map(d => dataSourceOf(d))).toEqual(DATASETS.map(() => 'local'))
    expect(apiDatasets()).toEqual([])
  })

  it('?data=api forces the API for everything and the choice is remembered', () => {
    at('?data=api')
    expect(localDataEnabled()).toBe(false)
    expect(localDatasets()).toEqual([])
    expect(apiDatasets().sort()).toEqual([...DATASETS].sort())
    expect(localStorage.getItem(DATA_FLAG_KEY)).toBe('api')
    at('')
    expect(DATASETS.map(d => dataSourceOf(d))).toEqual(DATASETS.map(() => 'api'))             // remembered
  })

  it('?data=local goes back to the default after the API was forced', () => {
    at('?data=api')
    localDataEnabled()
    at('?data=local')
    expect(localDatasets().sort()).toEqual([...DATASETS].sort())
    at('')
    expect(localDataEnabled()).toBe(true)
  })

  it('?data=local:a,b turns only those on, and the others read the API', () => {
    at('?data=local:team-report,report-teams')
    expect(dataSourceOf('team-report')).toBe('local')
    expect(dataSourceOf('report-teams')).toBe('local')
    expect(dataSourceOf('team-stats')).toBe('api')
    expect(dataSourceOf('player-stats')).toBe('api')
    expect(apiDatasets()).toContain('team-stats')
    at('')
    expect(localDatasets().sort()).toEqual(['report-teams', 'team-report'])                 // remembered
  })

  it('a newer ?data replaces the remembered one', () => {
    at('?data=api')
    localDataEnabled()
    at('?data=local:team-stats')
    expect(localDatasets()).toEqual(['team-stats'])
    at('')
    expect(localDatasets()).toEqual(['team-stats'])
  })

  it.each([
    ['local:no-such-dataset', []],                              // a typo turns nothing on (and nothing breaks)
    ['local:', []],
    ['local:team-stats,no-such-dataset', ['team-stats']],       // the valid ones of a list still count
    ['local:team-stats,team-stats', ['team-stats']],            // once
  ])('?data=%s', (asked, expected) => {
    at(`?data=${asked}`)
    expect(localDatasets()).toEqual(expected)
  })

  it.each(['LOCAL', 'API', 'something-else'])('?data=%s is not a choice: it is ignored and the default stays', (asked) => {
    at(`?data=${asked}`)
    expect(localDatasets().length).toBe(DATASETS.length)
    expect(localStorage.getItem(DATA_FLAG_KEY)).toBeNull()
  })

  it('a damaged remembered value is the default, not a broken page', () => {
    localStorage.setItem(DATA_FLAG_KEY, 'garbage')
    expect(localDatasets().length).toBe(DATASETS.length)
  })

  it('without storage (private window, blocked) the default is local, ?data=api still works for the page and nothing throws', () => {
    const getItem = Storage.prototype.getItem
    const setItem = Storage.prototype.setItem
    Storage.prototype.getItem = () => { throw new Error('blocked') }
    Storage.prototype.setItem = () => { throw new Error('blocked') }
    try {
      expect(localDataEnabled()).toBe(true)
      expect(dataSourceOf('team-report')).toBe('local')
      at('?data=api')
      expect(dataSourceOf('team-report')).toBe('api')
    } finally {
      Storage.prototype.getItem = getItem
      Storage.prototype.setItem = setItem
    }
  })
})
