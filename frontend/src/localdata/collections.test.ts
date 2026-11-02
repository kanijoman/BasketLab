import { describe, expect, it } from 'vitest'
import { collectionList } from './collections'
import vectors from '../../../tests/local_vectors/collections.json'

// The list of competitions on the device (issue #705): the manifest of the publication (name, league, games) and the components of the name give the very list
// `CollectionService.list_available` answers (`tests/local_vectors/collection_vectors.py`: the real collections of a working copy, with their accents and ordinals).
describe('the list of competitions from the manifest', () => {
  it('is the list of the API, row for row and in its order', () => {
    expect(collectionList(vectors.published as never)).toEqual(vectors.listed)
  })

  it('does not depend on the order of the manifest', () => {
    expect(collectionList([...(vectors.published as never[])].reverse() as never)).toEqual(vectors.listed)
  })

  it('has nothing when the publication has no competitions', () => {
    expect(collectionList([])).toEqual([])
  })

  it('a name without a season is its own competition with no season and no group', () => {
    expect(collectionList([{ collection: 'EXTRA', league: 'feb', games: 3 }] as never)).toEqual([{ name: 'EXTRA', league: 'FEB', competition: 'EXTRA', season: '', group: '', game_count: 3 }])
  })
})
