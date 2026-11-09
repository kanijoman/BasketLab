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

// Issue #452, block 2 (zones): the files that carry `zone_system: 'engine'` use the zones of `live_core.zones` (the ones the app and the scouting reports say); a file without it is the old
// system (the vectors above). The reader knows both so the data can change after the web does (deployment protocol: first the one that reads, then the one that writes).
describe('the zone system of a file', () => {
  const ENGINE = ['restricted_area', 'key_area', 'short_mid_range', 'medium_mid_range', 'long_mid_range', 'left_corner_three', 'left_wing_three', 'center_three', 'right_wing_three', 'right_corner_three']
  const file = (rows: Shots['shots'], zoneSystem?: string) => ({ format: 1, collection: 'X', league: 'feb', games: 1, columns: [], shots: rows, ...(zoneSystem ? { zone_system: zoneSystem } : {}) }) as unknown as Shots
  const rows: Shots['shots'] = [['T1', 'P1', 7.5, 3, true, 'key_area'], ['T1', 'P1', 7.5, 3, false, 'key_area'], ['T1', 'P2', 0.4, 1, true, 'left_corner_three'], ['T1', 'P2', 1, 1, true, 'paint']]

  it('a file of the engine system lists the 10 zones of the engine, in its order, with their labels and points', () => {
    const zones = shotZones(file(rows, 'engine'), {})
    expect(zones.map(z => z.zone)).toEqual(ENGINE)
    expect(zones.map(z => z.points)).toEqual([2, 2, 2, 2, 2, 3, 3, 3, 3, 3])
    expect(zones.find(z => z.zone === 'key_area')).toMatchObject({ zone_label: 'Zona', fga: 2, fgm: 1, fg_pct: 50 })
    expect(zones.find(z => z.zone === 'left_corner_three')).toMatchObject({ zone_label: 'Esquina Izq.', fga: 1, fgm: 1 })
  })

  it('a shot of the other system in a file of the engine counts for no zone (it cannot be told apart, and a wrong zone is worse)', () => {
    expect(shotZones(file(rows, 'engine'), {}).reduce((sum, z) => sum + z.fga, 0)).toBe(3)
  })

  it('a file without zone_system is the old system: its zones and not the engine ones', () => {
    const zones = shotZones(file(rows), {})
    expect(zones.map(z => z.zone)).toEqual(['restricted_area', 'paint', 'mid_left', 'mid_center', 'mid_right', 'corner_left', 'wing_left', 'top_three', 'wing_right', 'corner_right'])
    expect(zones.find(z => z.zone === 'paint')!.fga).toBe(1)
  })

  it('the rating against the league uses the zones of the file too', () => {
    const many: Shots['shots'] = Array.from({ length: 24 }, (_, i) => [i % 2 ? 'T1' : 'T2', `P${i % 4}`, 7.5, 3, i % 3 === 0, 'key_area'])
    const rated = shotZones(file(many, 'engine'), { team_id: 'T1', compare: 'league' })
    expect(rated.find(z => z.zone === 'key_area')).toMatchObject({ rating: expect.stringMatching(/above|below|average/) })
    expect(rated.find(z => z.zone === 'left_corner_three')).toMatchObject({ rating: 'none' })
  })
})
