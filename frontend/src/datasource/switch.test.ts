import { beforeEach, describe, expect, it } from 'vitest'
import { DATASETS, DATA_FLAG_KEY, dataSourceOf, localDatasets, localDataEnabled } from './switch'

// The switch of the local-first migration (issue #329): which datasets the web reads from the published files and which from the API, so that pages
// move one at a time instead of all at once. `?data=local` = all of them, `?data=local:team-report,team-stats` = only those, `?data=api` = none.
// The choice is remembered in the browser.
const at = (search: string) => window.history.replaceState(null, '', `/x${search}`)

beforeEach(() => { localStorage.clear(); at('') })

describe('which datasets read the local files', () => {
  it('none by default: everything comes from the API', () => {
    expect(localDataEnabled()).toBe(false)
    expect(localDatasets()).toEqual([])
    expect(DATASETS.map(d => dataSourceOf(d))).toEqual(DATASETS.map(() => 'api'))
  })

  it('?data=local turns every dataset on, and the choice is remembered', () => {
    at('?data=local')
    expect(localDatasets().sort()).toEqual([...DATASETS].sort())
    at('')
    expect(localDataEnabled()).toBe(true)
    expect(localStorage.getItem(DATA_FLAG_KEY)).toBe('local')
  })

  it('?data=local:a,b turns only those on, and the others keep reading the API', () => {
    at('?data=local:team-report,report-teams')
    expect(dataSourceOf('team-report')).toBe('local')
    expect(dataSourceOf('report-teams')).toBe('local')
    expect(dataSourceOf('team-stats')).toBe('api')
    expect(dataSourceOf('player-stats')).toBe('api')
    at('')
    expect(localDatasets().sort()).toEqual(['report-teams', 'team-report'])                 // remembered
  })

  it('?data=api turns everything off and forgets the choice', () => {
    at('?data=local')
    localDataEnabled()
    at('?data=api')
    expect(localDataEnabled()).toBe(false)
    expect(localStorage.getItem(DATA_FLAG_KEY)).toBeNull()
    at('')
    expect(localDatasets()).toEqual([])
  })

  it('a newer ?data replaces the remembered one', () => {
    at('?data=local')
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
    ['LOCAL', []],                                              // exact words only
    ['something-else', []],
  ])('?data=%s', (asked, expected) => {
    at(`?data=${asked}`)
    expect(localDatasets()).toEqual(expected)
  })

  it('without storage (private window, blocked) the API is used and nothing throws', () => {
    const original = Storage.prototype.getItem
    Storage.prototype.getItem = () => { throw new Error('blocked') }
    try {
      expect(localDataEnabled()).toBe(false)
      expect(dataSourceOf('team-report')).toBe('api')
    } finally {
      Storage.prototype.getItem = original
    }
  })
})
