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

  // #884: the external sources are competitions of their own; their ámbito is their source, never FEB by default
  it('lists an external competition under its own source and keeps the other two as they were', () => {
    const list = collectionList([
      { collection: 'NCAA_D1_2026_SEC', league: 'ncaa', games: 30 },
      { collection: 'FIBA_U18_EuroBasket_2026_', league: 'fiba', games: 6 },
      { collection: 'ACB_Liga_Endesa_2026_', league: 'acb', games: 9 },
      { collection: 'PRIMERA_FEB_2025_2026_Liga_Regular_Único', league: 'feb', games: 10 },
      { collection: 'FBCYL_1ª_FASE-GRUPO_A-1_2026_', league: 'fbcyl', games: 4 },
    ] as never)
    expect(Object.fromEntries(list.map(c => [c.name, c.league]))).toEqual({
      NCAA_D1_2026_SEC: 'NCAA', FIBA_U18_EuroBasket_2026_: 'FIBA', ACB_Liga_Endesa_2026_: 'ACB', PRIMERA_FEB_2025_2026_Liga_Regular_Único: 'FEB', 'FBCYL_1ª_FASE-GRUPO_A-1_2026_': 'FBCYL',
    })
  })
})
