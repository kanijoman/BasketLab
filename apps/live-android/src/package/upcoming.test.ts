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


describe('the list of matches to follow: the next match of each team that passes the filters (issues #510, #511)', () => {
  const NONE = { league: '', competition: '', group: '', team: '', onlyFavorites: false }
  const info = (competition: string, group = '') => ({ key: competition, label: group ? `${competition} · ${group}` : competition, competition, group, season: '2026/2027', league: 'FEB', level: 3, gender: 'M' as const })
  const rounds = (): RoundIndexEntry[] => [
    { ...round('SEGUNDA_A', [match('1', ['1008857', 'CULTURAL Y DEPORTIVA LEONESA'], ['2', 'ZAMORA'], '2026-10-24T19:30'), match('2', ['3', 'GETAFE'], ['4', 'TOLEDO'], '2026-10-24T18:00')]), competition: info('SEGUNDA FEB', 'A') },
    { ...round('SEGUNDA_A_NEXT', [match('5', ['2', 'ZAMORA'], ['3', 'GETAFE'], '2026-10-31T19:30')]), competition: info('SEGUNDA FEB', 'A') },
    { ...round('TERCERA', [match('9', ['7', 'MARÍN'], ['8', 'COYA'], '2026-10-25T12:00')]), competition: info('TERCERA FEB', 'A-B') },
  ]

  it('shows only the next match of each team: the following round of the same teams is not listed', async () => {
    const { nextMatchList } = await import('./upcoming')
    const codes = nextMatchList(rounds(), NONE, [], NOW).map(n => n.match.code)
    expect(codes).toEqual(expect.arrayContaining(['1', '2', '9']))
    expect(codes).not.toContain('5')
  })

  it('lists the matches by date when nobody is of interest', async () => {
    const { nextMatchList } = await import('./upcoming')
    expect(nextMatchList(rounds(), NONE, [], NOW).map(n => n.match.code)).toEqual(['2', '1', '9'])
  })

  it('by default, with teams of interest, the list is only their next match (feedback 0.4.0, #569)', async () => {
    const { nextMatchList } = await import('./upcoming')
    expect(nextMatchList(rounds(), NONE, [{ teamId: '7', name: 'MARÍN' }], NOW).map(n => n.match.code)).toEqual(['9'])
    expect(nextMatchList(rounds(), NONE, [{ teamId: '7', name: 'MARÍN' }, { teamId: '2', name: 'ZAMORA' }], NOW).map(n => n.match.code)).toEqual(['1', '9'])
  })

  it('once a filter is chosen the list is what the user asked for, with the matches of the teams of interest first', async () => {
    const { nextMatchList } = await import('./upcoming')
    const zamora = [{ teamId: '2', name: 'ZAMORA' }]
    expect(nextMatchList(rounds(), { ...NONE, competition: 'SEGUNDA FEB' }, zamora, NOW).map(n => n.match.code)).toEqual(['1', '2'])   // Zamora's, then the rest of the round
    expect(nextMatchList(rounds(), { ...NONE, competition: 'TERCERA FEB' }, zamora, NOW).map(n => n.match.code)).toEqual(['9'])        // the favourite does not play there: all the same
  })

  it('a postponed or brought-forward match is the next one by date, not by round (#569)', async () => {
    const { nextMatchList } = await import('./upcoming')
    const leonesa = [{ teamId: '1008857', name: 'CULTURAL Y DEPORTIVA LEONESA' }]
    const moved = [
      { ...round('R6', [match('20', ['1008857', 'CULTURAL Y DEPORTIVA LEONESA'], ['9', 'X'], '2026-11-14T19:30')]), round: 6, competition: info('SEGUNDA FEB', 'A') },
      { ...round('R5', [match('21', ['1008857', 'CULTURAL Y DEPORTIVA LEONESA'], ['8', 'Y'], '2026-11-07T19:30')]), round: 5, competition: info('SEGUNDA FEB', 'A') },
      { ...round('R4_POSTPONED', [match('22', ['1008857', 'CULTURAL Y DEPORTIVA LEONESA'], ['7', 'Z'], '2026-10-28T20:00')]), round: 4, competition: info('SEGUNDA FEB', 'A') },
    ]
    expect(nextMatchList(moved, NONE, leonesa, NOW).map(n => n.match.code)).toEqual(['22'])
  })

  it('only the matches of the chosen competition and group are listed', async () => {
    const { nextMatchList } = await import('./upcoming')
    expect(nextMatchList(rounds(), { ...NONE, competition: 'TERCERA FEB' }, [], NOW).map(n => n.match.code)).toEqual(['9'])
    expect(nextMatchList(rounds(), { ...NONE, competition: 'SEGUNDA FEB', group: 'B' }, [], NOW)).toEqual([])
  })

  it('a team chosen shows only its next match', async () => {
    const { nextMatchList } = await import('./upcoming')
    expect(nextMatchList(rounds(), { ...NONE, competition: 'SEGUNDA FEB', team: '2' }, [], NOW).map(n => n.match.code)).toEqual(['1'])
  })

  it('a match that has ended is not listed, and the next one of that team takes its place', async () => {
    const { nextMatchList } = await import('./upcoming')
    const past = [{ ...round('A', [match('10', ['3', 'GETAFE'], ['4', 'TOLEDO'], '2026-10-20T18:00'), match('11', ['3', 'GETAFE'], ['5', 'PRAT'], '2026-10-27T18:00')]), competition: info('SEGUNDA FEB', 'A') }]
    expect(nextMatchList(past, { ...NONE, team: '3' }, [], NOW).map(n => n.match.code)).toEqual(['11'])
  })

  describe('which side is followed', () => {
    const FAVORITE_HOME = [{ teamId: '1008857', name: 'CULTURAL Y DEPORTIVA LEONESA' }]

    it('without teams of interest, either side', async () => {
      const { nextMatchList } = await import('./upcoming')
      expect(nextMatchList(rounds(), NONE, [], NOW).find(n => n.match.code === '1')!.sides).toEqual(['1008857', '2'])
    })

    it('a favourite is always the side followed, without offering the other', async () => {
      const { nextMatchList } = await import('./upcoming')
      expect(nextMatchList(rounds(), NONE, FAVORITE_HOME, NOW).find(n => n.match.code === '1')!.sides).toEqual(['1008857'])
      expect(nextMatchList(rounds(), NONE, [{ teamId: '2', name: 'ZAMORA' }], NOW).find(n => n.match.code === '1')!.sides).toEqual(['2'])
    })

    it('when two favourites play each other the user chooses', async () => {
      const { nextMatchList } = await import('./upcoming')
      const both = [...FAVORITE_HOME, { teamId: '2', name: 'ZAMORA' }]
      expect(nextMatchList(rounds(), NONE, both, NOW).find(n => n.match.code === '1')!.sides).toEqual(['1008857', '2'])
    })
  })
})
