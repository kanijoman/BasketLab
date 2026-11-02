import { describe, expect, it } from 'vitest'
import { playerQuartiles } from './playerQuartiles'
import vectors from '../../../tests/local_vectors/player_quartiles.json'

// The quartiles of the players on the device (issue #707): `PlayerStatsService.get_quartiles` over a table, exactly (`tests/local_vectors/quartile_vectors.py`; not rounded:
// the last digit of a float is part of the contract, so numpy's interpolation is the one reproduced).
describe.each([['FEB', vectors.feb], ['FBCYL', vectors.fbcyl], ['a table of awkward floats', vectors.awkward]] as const)('%s', (_name, vector) => {
  it('gives the quartiles of the API, field by field, bit for bit', () => {
    expect(playerQuartiles(vector.players as never)).toEqual(vector.quartiles)
  })
})

describe('the corners of the quartiles', () => {
  it('a field with fewer than four values (or none) has no entry, and players with fewer than three games do not count', () => {
    const players = [1, 2, 3, 4].map(n => ({ games_played: n < 4 ? 3 : 2, points_per_game: n }))
    expect(playerQuartiles(players as never)).toEqual({})
    expect(playerQuartiles([] as never)).toEqual({})
  })

  it('four values are enough: the quartiles interpolate between them', () => {
    const players = [1, 2, 3, 10].map(n => ({ games_played: 3, points_per_game: n }))
    expect(playerQuartiles(players as never).points_per_game).toEqual({ min: 1, q1: 1.75, q2: 2.5, q3: 4.75, max: 10, count: 4 })
  })
})
