import { describe, expect, it } from 'vitest'
import { orderRounds, type RoundIndexEntry, type RoundMatch } from './remote'
import { NO_FILTERS, competitionOf, filterRounds, leagueOf, loadFilters, optionsOf, saveFilters } from './filters'

const side = (id: string, name: string) => ({ id, name })
const match = (code: string, home: [string, string], away: [string, string], start = '2026-10-17T17:00', isClub = false): RoundMatch =>
  ({ code, start, home: side(...home), away: side(...away), own_id: home[0], is_club: isClub })
const round = (collection: string, matches: RoundMatch[], over: Partial<RoundIndexEntry> = {}): RoundIndexEntry =>
  ({ collection, round: 4, file: `rounds/${collection}.bpkgz`, sha256: 'x', bytes: 1, club: false, matches, ...over })

const info = (competition: string, group: string) => ({ key: 'k', label: `${competition} · ${group}`, competition, group, season: '2026/2027', level: 3, gender: 'M' as const })

const SEGUNDA_A = round('SEGUNDA_FEB_A', [match('1', ['1008857', 'CULTURAL Y DEPORTIVA LEONESA'], ['2', 'ZAMORA']), match('2', ['3', 'GETAFE'], ['4', 'TOLEDO'])],
  { competition: info('SEGUNDA FEB', 'Liga Regular "A"') })
const SEGUNDA_B = round('SEGUNDA_FEB_B', [match('3', ['1008978', 'LLÍRIA'], ['5', 'PRAT'])], { competition: info('SEGUNDA FEB', 'Liga Regular "B"') })
const TERCERA = round('TERCERA_FEB_AB', [match('4', ['1010490', 'CAJA RURAL RDL'], ['6', 'MIERES'])], { competition: info('TERCERA FEB', 'Liga Regular "A-B"') })
const OLD = round('LF_CHALLENGE_2026_Liga_Regular_Único', [match('5', ['7', 'ADBA'], ['8', 'ZAMORA'])])      // an index without competition data
const ALL = [SEGUNDA_A, SEGUNDA_B, TERCERA, OLD]
const favs = [{ teamId: '1008857', name: 'CULTURAL Y DEPORTIVA LEONESA' }]
const codes = (rounds: RoundIndexEntry[]) => rounds.flatMap(r => r.matches.map(m => m.code))

describe('competition of a round', () => {
  it('comes from the index when it has it', () => {
    expect(competitionOf(SEGUNDA_A)).toEqual({ name: 'SEGUNDA FEB', group: 'Liga Regular "A"', label: 'SEGUNDA FEB · Liga Regular "A"' })
  })

  it('an index without competition data falls back to the name of the collection', () => {
    expect(competitionOf(OLD)).toEqual({ name: 'LF CHALLENGE 2026 Liga Regular Único', group: '', label: 'LF CHALLENGE 2026 Liga Regular Único' })
  })
})

describe('filterRounds (issue #440)', () => {
  it('no filter keeps everything', () => {
    expect(filterRounds(ALL, NO_FILTERS, favs)).toEqual(ALL)
  })

  it('by competition and, inside it, by group', () => {
    expect(codes(filterRounds(ALL, { ...NO_FILTERS, competition: 'SEGUNDA FEB' }, []))).toEqual(['1', '2', '3'])
    expect(codes(filterRounds(ALL, { ...NO_FILTERS, competition: 'SEGUNDA FEB', group: 'Liga Regular "B"' }, []))).toEqual(['3'])
  })

  it('by team once a competition is chosen (a list, not a free text, issue #474)', () => {
    const only = (team: string) => codes(filterRounds(ALL, { ...NO_FILTERS, competition: 'SEGUNDA FEB', team }, []))
    expect(only('1008857')).toEqual(['1'])
    expect(only('5')).toEqual(['3'])
    expect(only('3')).toEqual(['2'])
  })

  it('a team of a competition that is not the chosen one gives nothing', () => {
    expect(codes(filterRounds(ALL, { ...NO_FILTERS, competition: 'TERCERA FEB', team: '1008857' }, []))).toEqual([])
  })

  it('a team that is not in the published rounds does not hide everything: the filter is ignored by the screen, not here', () => {
    expect(filterRounds(ALL, { ...NO_FILTERS, team: 'nobody' }, [])).toEqual([])
  })

  it('by league: FEB or FBCYL, from the competition data or from the name of the collection', () => {
    const fbcyl = round('FBCYL_1_FASE-GRUPO_A-1_2026_', [match('77', ['39609', 'UNILEON'], ['40083', 'HIJOLUSA'])])
    const mixed = [...ALL, fbcyl]
    expect(leagueOf(fbcyl)).toBe('FBCYL')
    expect(leagueOf(SEGUNDA_A)).toBe('FEB')
    expect(codes(filterRounds(mixed, { ...NO_FILTERS, league: 'FBCYL' }, []))).toEqual(['77'])
    expect(codes(filterRounds(mixed, { ...NO_FILTERS, league: 'FEB' }, []))).toEqual(['1', '2', '3', '4', '5'])
    expect(leagueOf({ ...SEGUNDA_A, competition: { ...info('X', 'A'), league: 'FBCYL' } })).toBe('FBCYL')       // what the publisher says wins
  })

  it('only the matches of teams of interest; the rounds left empty disappear', () => {
    const out = filterRounds(ALL, { ...NO_FILTERS, onlyFavorites: true }, favs)
    expect(out.map(r => r.collection)).toEqual(['SEGUNDA_FEB_A'])
    expect(codes(out)).toEqual(['1'])
  })

  it('«de interés» without teams of interest shows nothing', () => {
    expect(filterRounds(ALL, { ...NO_FILTERS, onlyFavorites: true }, [])).toEqual([])
  })

  it('a favourite is found by name when its id changed', () => {
    const renamed = [{ teamId: '1', name: 'Llíria' }]
    expect(codes(filterRounds(ALL, { ...NO_FILTERS, onlyFavorites: true }, renamed))).toEqual(['3'])
  })

  it('the filters combine', () => {
    expect(codes(filterRounds(ALL, { league: '', competition: 'SEGUNDA FEB', group: '', team: '2', onlyFavorites: false }, []))).toEqual(['1'])
  })

  it('does not change what it is given', () => {
    const before = JSON.stringify(ALL)
    filterRounds(ALL, { ...NO_FILTERS, competition: 'SEGUNDA FEB', team: '2' }, [])
    expect(JSON.stringify(ALL)).toBe(before)
  })
})

describe('options of the filters', () => {
  it('lists the competitions, and the groups of the chosen one (or none while it is not chosen)', () => {
    expect(optionsOf(ALL, NO_FILTERS).competitions).toEqual(['LF CHALLENGE 2026 Liga Regular Único', 'SEGUNDA FEB', 'TERCERA FEB'])
    expect(optionsOf(ALL, { ...NO_FILTERS, competition: 'SEGUNDA FEB' }).groups).toEqual(['Liga Regular "A"', 'Liga Regular "B"'])
    expect(optionsOf(ALL, NO_FILTERS).groups).toEqual([])
    expect(optionsOf(ALL, { ...NO_FILTERS, competition: 'LF CHALLENGE 2026 Liga Regular Único' }).groups).toEqual([])
  })

  it('lists the teams of the chosen competition and group, by name, once; none while no competition is chosen (issue #474)', () => {
    expect(optionsOf(ALL, NO_FILTERS).teams).toEqual([])
    const teams = (f: Partial<typeof NO_FILTERS>) => optionsOf(ALL, { ...NO_FILTERS, ...f }).teams.map(t => t.name)
    expect(teams({ competition: 'SEGUNDA FEB' })).toEqual(['CULTURAL Y DEPORTIVA LEONESA', 'GETAFE', 'LLÍRIA', 'PRAT', 'TOLEDO', 'ZAMORA'])
    expect(teams({ competition: 'SEGUNDA FEB', group: 'Liga Regular "B"' })).toEqual(['LLÍRIA', 'PRAT'])
    expect(optionsOf(ALL, { ...NO_FILTERS, competition: 'SEGUNDA FEB' }).teams[0]).toEqual({ id: '1008857', name: 'CULTURAL Y DEPORTIVA LEONESA' })
  })

  it('the leagues appear only when there is more than one', () => {
    expect(optionsOf(ALL, NO_FILTERS).leagues).toEqual([])
    const fbcyl = round('FBCYL_1_FASE-GRUPO_A-1_2026_', [match('77', ['39609', 'UNILEON'], ['40083', 'HIJOLUSA'])])
    expect(optionsOf([...ALL, fbcyl], NO_FILTERS).leagues).toEqual(['FBCYL', 'FEB'])
    expect(optionsOf([...ALL, fbcyl], { ...NO_FILTERS, league: 'FBCYL' }).competitions).toEqual(['FBCYL 1 FASE-GRUPO A-1 2026'])
  })
})

describe('the chosen filters are remembered on the device', () => {
  function memory(): Storage {
    const data = new Map<string, string>()
    return { getItem: k => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v), removeItem: k => void data.delete(k), clear: () => data.clear(), key: () => null, get length() { return data.size } }
  }

  it('saves and loads them', () => {
    const s = memory()
    saveFilters({ league: 'FEB', competition: 'SEGUNDA FEB', group: '', team: '1008857', onlyFavorites: true }, s)
    expect(loadFilters(s)).toEqual({ league: 'FEB', competition: 'SEGUNDA FEB', group: '', team: '1008857', onlyFavorites: true })
  })

  it('nothing saved, corrupted or half-written storage gives no filter', () => {
    const s = memory()
    expect(loadFilters(s)).toEqual(NO_FILTERS)
    s.setItem('basketlab-live-filters', 'no json')
    expect(loadFilters(s)).toEqual(NO_FILTERS)
    s.setItem('basketlab-live-filters', JSON.stringify({ competition: 3, onlyFavorites: 'yes', team: 'x', text: 'an old free text' }))
    expect(loadFilters(s)).toEqual({ ...NO_FILTERS, team: 'x' })
  })
})

describe('orderRounds with teams of interest', () => {
  it('the rounds with a team of interest come first, and in each round its matches first', () => {
    const out = orderRounds(ALL, favs)
    expect(out[0].collection).toBe('SEGUNDA_FEB_A')
    expect(out[0].matches.map(m => m.code)).toEqual(['1', '2'])
    expect(orderRounds([OLD, SEGUNDA_A].map(r => ({ ...r, matches: [...r.matches].reverse() })), favs)[0].matches.map(m => m.code)).toEqual(['1', '2'])
  })

  it('without favourites it is exactly what it was (club first, then by name)', () => {
    const withClub = [round('B', [match('9', ['1', 'X'], ['2', 'Y'])]), round('A', [match('8', ['3', 'Z'], ['4', 'W'])], { club: true })]
    expect(orderRounds(withClub).map(r => r.collection)).toEqual(['A', 'B'])
    expect(orderRounds(withClub, []).map(r => r.collection)).toEqual(['A', 'B'])
  })
})
