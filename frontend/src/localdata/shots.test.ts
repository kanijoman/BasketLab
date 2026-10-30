import { describe, expect, it } from 'vitest'
import { shotRaw, shotZones, type Shots } from './shots'
import febVectors from '../../../tests/local_vectors/shots_feb.json'
import fbcylVectors from '../../../tests/local_vectors/shots_fbcyl.json'

// Tiros on the device (issue #685): the zones of a team, a player or the league, their rating against the league and the raw shots equal what the real endpoints answer
// (`tests/local_vectors/generate.py`: `get_shot_zones` and `get_shot_raw` over the shots of the fixture games, in both leagues).
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }

function expectSame(actual: unknown, expected: Json, path = '$'): void {
  if (typeof expected === 'number') {
    expect(typeof actual, path).toBe('number')
    expect(actual as number, path).toBeCloseTo(expected, 9)
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true)
    expect((actual as unknown[]).length, path).toBe(expected.length)
    expected.forEach((item, i) => expectSame((actual as unknown[])[i], item, `${path}[${i}]`))
  } else if (expected !== null && typeof expected === 'object') {
    expect(actual, path).not.toBeNull()
    expect(Object.keys(actual as object).sort(), path).toEqual(Object.keys(expected).sort())
    for (const [key, value] of Object.entries(expected)) expectSame((actual as Record<string, unknown>)[key], value, `${path}.${key}`)
  } else {
    expect(actual, path).toEqual(expected)
  }
}

describe.each([['FEB', febVectors], ['FBCYL', fbcylVectors]] as const)('%s: the shot tables equal what the API answers', (_league, vectors) => {
  const shots = vectors.payload as unknown as Shots

  it.each(vectors.zones.map((c, i) => [`${JSON.stringify(c.filter)} ${c.compare ?? 'no comparison'} (${i})`, c] as const))('zones: %s', (_name, c) => {
    const filter = c.filter as { team_id?: string; player?: string }
    expectSame(shotZones(shots, { ...filter, compare: (c.compare ?? undefined) as 'league' | undefined }), c.zones as unknown as Json)
  })

  it.each(vectors.raw.map((c, i) => [`${JSON.stringify(c.filter)} limit ${c.limit} (${i})`, c] as const))('raw: %s', (_name, c) => {
    expectSame(shotRaw(shots, { ...(c.filter as { team_id?: string; player?: string }), limit: c.limit }), c.shots as unknown as Json)
  })
})

describe('the shot tables: the corners', () => {
  const none: Shots = { format: 1, collection: 'C', league: 'feb', games: 0, columns: ['team_id', 'player_id', 'x', 'y', 'made', 'zone'], shots: [] }

  it('no shot is ten empty zones, not an error, and the raw list is empty', () => {
    const zones = shotZones(none, {})
    expect(zones).toHaveLength(10)
    expect(zones.every(z => z.fga === 0 && z.fgm === 0 && z.fg_pct === 0)).toBe(true)
    expect(shotRaw(none, {})).toEqual([])
  })

  it('the raw shots are cut at the limit the API caps (10000) and default to 5000', () => {
    const many: Shots = { ...none, shots: Array.from({ length: 12000 }, () => ['1', 'p', 7.5, 3, true, 'paint']) }
    expect(shotRaw(many, {})).toHaveLength(5000)
    expect(shotRaw(many, { limit: 10000 })).toHaveLength(10000)
  })
})
