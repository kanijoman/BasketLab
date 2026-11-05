import { describe, expect, it } from 'vitest'
import type { CollectionInfo } from '@/api/client'
import { collectionList } from '@/localdata/collections'
import { collectionLabel, levelsOf, pickCollection, selectionOf } from './collectionPicker'

// Issue #761: the competition is chosen by ámbito → temporada → competición → grupo, each level filtered by the previous ones.
const c = (name: string, league: string, competition: string, season: string, group = ''): CollectionInfo =>
  ({ name, league, competition, season, group, game_count: 10 }) as CollectionInfo

const LIST = [
  c('FEB_LF2_25_A', 'FEB', 'LF2', '2025_2026', 'A'),
  c('FEB_LF2_25_B', 'FEB', 'LF2', '2025_2026', 'B'),
  c('FEB_LF2_24_A', 'FEB', 'LF2', '2024_2025', 'A'),
  c('FEB_LF1_25', 'FEB', 'LF1', '2025_2026'),
  c('FBCYL_U16_25', 'FBCYL', 'U16', '2025_2026'),
  c('AND_SEN_25', 'ANDALUCIA', 'Senior', '2025_2026'),
]

describe('pickCollection (issue #761)', () => {
  it('lists the ámbitos of the data: FEB and FBCYL first, the others (new federations) after, in order', () => {
    expect(pickCollection(LIST, {}).ambitos).toEqual(['FEB', 'FBCYL', 'ANDALUCIA'])
    expect(pickCollection([c('z', 'MADRID', 'S', '2025'), c('a', 'ARAGON', 'S', '2025'), c('f', 'FBCYL', 'S', '2025')], {}).ambitos).toEqual(['FBCYL', 'ARAGON', 'MADRID'])
  })

  it('with nothing chosen it preselects the latest season, the first competition and the first group', () => {
    const p = pickCollection(LIST, {})
    expect(p.selection).toEqual({ ambito: 'FEB', season: '2025/2026', competition: 'LF1', group: '' })
    expect(p.seasons).toEqual(['2025/2026', '2024/2025'])
    expect(p.collection?.name).toBe('FEB_LF1_25')
  })

  it('each level only offers what the previous ones allow', () => {
    const p = pickCollection(LIST, { ambito: 'FEB', season: '2024/2025' })
    expect(p.competitions).toEqual(['LF2'])
    expect(p.groups).toEqual(['A'])
    expect(pickCollection(LIST, { ambito: 'FBCYL' }).competitions).toEqual(['U16'])
  })

  it('a choice that does not exist at the new level falls back to the default instead of leaving an impossible combination', () => {
    // LF1 exists only in 2025-2026: moving to 2024-2025 cannot keep it
    expect(pickCollection(LIST, { ambito: 'FEB', season: '2024/2025', competition: 'LF1' }).selection.competition).toBe('LF2')
    // the ámbito changes: the season of the old one is not offered by the new one
    expect(pickCollection(LIST, { ambito: 'ANDALUCIA', season: '2024/2025' }).collection?.name).toBe('AND_SEN_25')
  })

  it('keeps the competition and the group when they still exist after changing the season', () => {
    const p = pickCollection(LIST, { ambito: 'FEB', season: '2024/2025', competition: 'LF2', group: 'A' })
    expect(p.collection?.name).toBe('FEB_LF2_24_A')
    expect(pickCollection(LIST, { ambito: 'FEB', season: '2025/2026', competition: 'LF2', group: 'B' }).collection?.name).toBe('FEB_LF2_25_B')
  })

  it('a competition without groups has a single empty group (nothing to show)', () => {
    expect(pickCollection(LIST, { competition: 'LF1' }).groups).toEqual([''])
  })

  it('an empty list gives no options and no collection', () => {
    expect(pickCollection([], {})).toMatchObject({ ambitos: [], seasons: [], competitions: [], groups: [], collection: null })
  })

  it('selectionOf gives the levels of a collection, so the header starts on the current one', () => {
    expect(selectionOf(LIST[1])).toEqual({ ambito: 'FEB', season: '2025/2026', competition: 'LF2', group: 'B' })
    expect(pickCollection(LIST, selectionOf(LIST[1])).collection?.name).toBe('FEB_LF2_25_B')
  })
})

// The levels are read from the real names of the published competitions (parsed as the web parses them), not from invented fields: the season is the year(s) only, the competition its
// name, and the group what tells the collections of a competition apart (the phase and the group: «Liga Regular A», «Play-offs 1/2 Final»).
const NAMES: [string, 'feb' | 'fbcyl'][] = [
  ...['A', 'B', 'C'].map(g => [`COPA_ESPAÑA_2025_2026_FASE_DE_GRUPOS_${g}`, 'feb'] as [string, 'feb']),
  ['COPA_ESPAÑA_2025_2026_Play-offs_1_8_Final', 'feb'], ['COPA_ESPAÑA_2025_2026_Play-offs_Final', 'feb'],
  ['FBCYL_1ª_FASE-GRUPO_A-1_2026_', 'fbcyl'],
  ['LF_CHALLENGE_2026_2027_Liga_Regular_Único', 'feb'], ['LF_ENDESA_2026_2027_Liga_Regular_Único', 'feb'],
  ['LIGA_U_2026_2027_LIGA_REGULAR_GRUPO_A', 'feb'], ['LIGA_U_2026_2027_LIGA_REGULAR_GRUPO_B', 'feb'],
  ['PRIMERA_FEB_2025_2026_Liga_Regular_Único', 'feb'], ['PRIMERA_FEB_2025_2026_Play-offs_1_2_Final', 'feb'], ['PRIMERA_FEB_2025_2026_Play-offs_Final', 'feb'],
  ['PRIMERA_FEB_2026_2027_Liga_Regular_Único', 'feb'],
  ['SEGUNDA_FEB_2025_2026_1ªE-1ªO_Final', 'feb'], ['SEGUNDA_FEB_2025_2026_ELIMINATORIAS_1_8_Final', 'feb'], ['SEGUNDA_FEB_2025_2026_Liga_Regular_ESTE', 'feb'],
  ['SEGUNDA_FEB_2026_2027_Liga_Regular_A', 'feb'], ['SEGUNDA_FEB_2026_2027_Liga_Regular_B', 'feb'],
  ['TERCERA_FEB_2026_2027_Liga_Regular_A-B', 'feb'],
]
const REAL = collectionList(NAMES.map(([collection, league]) => ({ collection, league, games: 10 })))

describe('levels of the real competitions', () => {
  it('the season is only the year(s)', () => {
    expect(pickCollection(REAL, { ambito: 'FEB' }).seasons).toEqual(['2026/2027', '2025/2026'])
    expect(pickCollection(REAL, { ambito: 'FBCYL' }).seasons).toEqual(['2026/2027'])           // FBCYL names only the year the season starts in (`_season` 2026, first game on 3/10/2026)
  })

  it('the competition is its name, without the underscores of the slug', () => {
    expect(pickCollection(REAL, { ambito: 'FEB', season: '2026/2027' }).competitions)
      .toEqual(['LF CHALLENGE', 'LF ENDESA', 'LIGA U', 'PRIMERA FEB', 'SEGUNDA FEB', 'TERCERA FEB'])
    expect(pickCollection(REAL, { ambito: 'FEB', season: '2025/2026' }).competitions).toContain('COPA ESPAÑA')
  })

  it('the group is the phase and the group, the regular league first', () => {
    const groups = (competition: string, season: string) => pickCollection(REAL, { ambito: 'FEB', season, competition }).groups
    expect(groups('SEGUNDA FEB', '2026/2027')).toEqual(['Liga Regular A', 'Liga Regular B'])
    expect(groups('PRIMERA FEB', '2026/2027')).toEqual(['Liga Regular'])                       // the only group of a league is not repeated as «Único»
    expect(groups('PRIMERA FEB', '2025/2026')).toEqual(['Liga Regular', 'Play-offs 1/2 Final', 'Play-offs Final'])
    expect(groups('SEGUNDA FEB', '2025/2026')).toEqual(['Liga Regular ESTE', '1ªE-1ªO Final', 'ELIMINATORIAS 1/8 Final'])
    expect(groups('LIGA U', '2026/2027')).toEqual(['LIGA REGULAR GRUPO A', 'LIGA REGULAR GRUPO B'])
    expect(groups('TERCERA FEB', '2026/2027')).toEqual(['Liga Regular A-B'])
    expect(groups('COPA ESPAÑA', '2025/2026')).toEqual(['FASE DE GRUPOS A', 'FASE DE GRUPOS B', 'FASE DE GRUPOS C', 'Play-offs 1/8 Final', 'Play-offs Final'])
  })

  it('every published collection is reachable from its own levels, and only from them', () => {
    for (const c of REAL) expect(pickCollection(REAL, selectionOf(c)).collection?.name).toBe(c.name)
  })

  it('the FBCYL phase is its group, and its competition has a name people know', () => {
    const p = pickCollection(REAL, { ambito: 'FBCYL' })
    expect(p.selection).toMatchObject({ season: '2026/2027', competition: '1ª División Femenina', group: 'FASE-GRUPO A-1' })
    expect(collectionLabel(p.collection!)).toBe('1ª División Femenina 2026/2027 · FASE-GRUPO A-1')
  })

  it('a single year is the year the season starts in: 2026 is 2026/2027, and two years are shown as they are', () => {
    const one = (season: string) => levelsOf({ name: 'x', league: 'FBCYL', competition: 'C', season, group: '', game_count: 1 }).season
    expect([one('FASE 2026'), one('2026_2027_Liga'), one('2025 FASE')]).toEqual(['2026/2027', '2026/2027', '2025/2026'])
  })

  it('an FBCYL competition without a known name is shown as the data gives it; FEB names are never renamed', () => {
    const list = collectionList([{ collection: 'FBCYL_U16_2026_FASE_1', league: 'fbcyl', games: 3 }, { collection: 'PRIMERA_FEB_2026_2027_Liga_Regular_Único', league: 'feb', games: 3 }])
    expect(levelsOf(list.find(c => c.league === 'FBCYL')!).competition).toBe('U16')
    expect(levelsOf(list.find(c => c.league === 'FEB')!).competition).toBe('PRIMERA FEB')
    expect(levelsOf({ ...list[0], league: 'FEB', competition: '1ª' }).competition).toBe('1ª')           // the table is only for FBCYL
  })

  it('names a collection by its competition, season and group', () => {
    expect(collectionLabel(REAL.find(c => c.name.startsWith('SEGUNDA_FEB_2026_2027_Liga_Regular_B'))!)).toBe('SEGUNDA FEB 2026/2027 · Liga Regular B')
    expect(collectionLabel(REAL.find(c => c.name.startsWith('PRIMERA_FEB_2026_2027'))!)).toBe('PRIMERA FEB 2026/2027 · Liga Regular')
  })
})
