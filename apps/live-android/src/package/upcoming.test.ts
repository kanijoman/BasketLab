import { describe, expect, it } from 'vitest'
import type { RoundIndexEntry, RoundMatch } from './remote'
import { nextMatchesOfFavorites } from './upcoming'

const side = (id: string, name: string) => ({ id, name })
const match = (code: string, home: [string, string], away: [string, string], start: string | null): RoundMatch =>
  ({ code, start, home: side(...home), away: side(...away), own_id: home[0], own_ids: [home[0], away[0]], is_club: false })
const round = (collection: string, matches: RoundMatch[]): RoundIndexEntry =>
  ({ collection, round: 4, file: `rounds/${collection}.bpkgz`, sha256: 'x', bytes: 1, club: false, matches })

const NOW = new Date('2026-10-22T12:00:00')
const LEONESA = { teamId: '1008857', name: 'CULTURAL Y DEPORTIVA LEONESA' }
const LLIRIA = { teamId: '1008978', name: 'LLÍRIA' }

const ROUNDS = [
  round('SEGUNDA_A', [match('1', ['1008857', 'CULTURAL Y DEPORTIVA LEONESA'], ['2', 'ZAMORA'], '2026-10-24T19:30'), match('2', ['3', 'GETAFE'], ['4', 'TOLEDO'], '2026-10-24T18:00')]),
  round('SEGUNDA_B', [match('3', ['5', 'PRAT'], ['1008978', 'LLÍRIA'], '2026-10-25T12:00')]),
]

describe('the next match of each team of interest (issue #478, feedback of 0.3.2)', () => {
  it('finds the next match of each favourite, in date order', () => {
    const next = nextMatchesOfFavorites(ROUNDS, [LLIRIA, LEONESA], NOW)
    expect(next.map(n => [n.favorite.name, n.match.code])).toEqual([['CULTURAL Y DEPORTIVA LEONESA', '1'], ['LLÍRIA', '3']])
  })

  it('says which side of the match the favourite is, to follow it as that team', () => {
    const [leonesa, lliria] = nextMatchesOfFavorites(ROUNDS, [LEONESA, LLIRIA], NOW)
    expect(leonesa.ownId).toBe('1008857')
    expect(lliria.ownId).toBe('1008978')
    expect(lliria.rival).toEqual({ id: '5', name: 'PRAT' })
  })

  it('a team without a match to come has none, and nobody marked gives nothing', () => {
    expect(nextMatchesOfFavorites(ROUNDS, [{ teamId: '999', name: 'OTRO' }], NOW)).toEqual([])
    expect(nextMatchesOfFavorites(ROUNDS, [], NOW)).toEqual([])
  })

  it('takes the nearest of several matches and leaves out the ones already played', () => {
    const rounds = [round('A', [match('10', ['1008857', 'LEONESA'], ['2', 'X'], '2026-10-10T18:00'), match('11', ['1008857', 'LEONESA'], ['3', 'Y'], '2026-11-01T18:00'), match('12', ['1008857', 'LEONESA'], ['4', 'Z'], '2026-10-23T18:00')])]
    expect(nextMatchesOfFavorites(rounds, [LEONESA], NOW).map(n => n.match.code)).toEqual(['12'])
  })

  it('a match that started a short while ago is still the next one (it may be on)', () => {
    const rounds = [round('A', [match('10', ['1008857', 'LEONESA'], ['2', 'X'], '2026-10-22T10:30')])]
    expect(nextMatchesOfFavorites(rounds, [LEONESA], NOW).map(n => n.match.code)).toEqual(['10'])
    expect(nextMatchesOfFavorites(rounds, [LEONESA], new Date('2026-10-22T14:30:00'))).toEqual([])
  })

  it('a favourite is found by name when its id changed, and a match without date goes last', () => {
    const rounds = [round('A', [match('10', ['77', 'Cultural y Deportiva Leónesa'], ['2', 'X'], null), match('11', ['78', 'LLIRIA'], ['5', 'PRAT'], '2026-10-24T12:00')])]
    expect(nextMatchesOfFavorites(rounds, [LLIRIA, LEONESA], NOW).map(n => n.match.code)).toEqual(['11', '10'])
  })

  it('two favourites in the same match give one line each, so each can be followed', () => {
    const rounds = [round('A', [match('10', ['1008857', 'LEONESA'], ['1008978', 'LLÍRIA'], '2026-10-24T12:00')])]
    const next = nextMatchesOfFavorites(rounds, [LEONESA, LLIRIA], NOW)
    expect(next.map(n => n.ownId)).toEqual(['1008857', '1008978'])
  })
})
