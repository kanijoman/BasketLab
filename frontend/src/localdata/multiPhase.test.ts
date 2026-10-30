import { describe, expect, it } from 'vitest'
import { mergeByKey, siblingCollections } from './multiPhase'
import vectors from '../../../tests/local_vectors/multi_phase.json'

// Multifase on the device (issue #671): the tables of several collections merged as `MultiPhaseService` does, and the phases (siblings) of a collection. The
// reference is Python (`tests/local_vectors/generate.py`): the service over two phases of each league, and `CollectionService.get_sibling_collections`.
type Row = Record<string, unknown>

/** Same keys and strings; numbers equal to the 2 decimals the service rounds to (a sum may differ in the last bit between Python and JS). */
function expectRows(actual: Row[], expected: Row[], key: string) {
  expect(actual.map(r => r[key])).toEqual(expected.map(r => r[key]))                 // the same entities in the same order (first appearance)
  expected.forEach((want, i) => {
    const got = actual[i]
    expect(Object.keys(got).sort(), String(want[key])).toEqual(Object.keys(want).sort())
    for (const [field, value] of Object.entries(want)) {
      if (typeof value === 'number') expect(got[field] as number, `${String(want[key])}.${field}`).toBeCloseTo(value, 2)
      else expect(got[field], `${String(want[key])}.${field}`).toEqual(value)
    }
  })
}

describe.each([['FEB', vectors.feb], ['FBCYL', vectors.fbcyl]] as const)('%s: the merged tables equal what the API answers', (_league, v) => {
  // in the order the service was given them (the JSON sorts its keys): the entities come in the order they first appear
  const phase = (pick: 'team_stats' | 'players') => Object.fromEntries((['PHASE_HOME', 'PHASE_AWAY'] as const).map(name => [name, v.phases[name][pick] as unknown as Row[]]))

  it('team table: one row per team with the phases added up and the ratios recomputed', () => {
    expectRows(mergeByKey(phase('team_stats'), 'team_name'), v.team_stats as unknown as Row[], 'team_name')
  })

  it('player table: one row per player name', () => {
    expectRows(mergeByKey(phase('players'), 'player_name'), v.players as unknown as Row[], 'player_name')
  })
})

describe('mergeByKey', () => {
  it('does not touch the tables it is given (the service renames fields in its own copy)', () => {
    const row = { team_name: 'A', total_games: 2, points_scored: 10 }
    const before = JSON.stringify(row)
    mergeByKey({ one: [row] }, 'team_name')
    expect(JSON.stringify(row)).toBe(before)
  })

  it('no tables, or rows with no name, is no rows', () => {
    expect(mergeByKey({}, 'team_name')).toEqual([])
    expect(mergeByKey({ one: [{ team_name: '', points_scored: 3 }] }, 'team_name')).toEqual([])
  })
})

describe('siblingCollections: the phases of a competition and season', () => {
  const { names, expected } = vectors.siblings
  it.each(Object.entries(expected))('%s', (name, want) => {
    expect(siblingCollections(name, names)).toEqual(want)
  })
})
