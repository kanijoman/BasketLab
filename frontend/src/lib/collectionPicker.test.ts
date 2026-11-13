import { readFileSync } from 'node:fs'
import { join } from 'node:path'
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
    expect(p.selection).toEqual({ ambito: 'FEB', category: 'Sénior', season: '2025/2026', competition: 'LF1', group: '' })
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
    expect(selectionOf(LIST[1])).toEqual({ ambito: 'FEB', category: 'Sénior', season: '2025/2026', competition: 'LF2', group: 'B' })
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
    expect(groups('SEGUNDA FEB', '2025/2026')).toEqual(['Liga Regular ESTE', 'ELIMINATORIAS 1/8 Final', '1ªE-1ªO Final'])       // #908: from the biggest draw to the final, not alphabetically
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
    expect(collectionLabel(p.collection!)).toBe('1ª División Femenina 2026/2027 FASE-GRUPO A-1')
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
    expect(collectionLabel(REAL.find(c => c.name.startsWith('SEGUNDA_FEB_2026_2027_Liga_Regular_B'))!)).toBe('SEGUNDA FEB 2026/2027 Liga Regular B')
    expect(collectionLabel(REAL.find(c => c.name.startsWith('PRIMERA_FEB_2026_2027'))!)).toBe('PRIMERA FEB 2026/2027 Liga Regular')
  })
})

// Issues #908 and #914: the youth competitions of FEB (formación) with the category, age group and name the REAL catalogue (`config/competitions.json`) gives them, as the selector shows them.
// The collections are REAL names of the publication; what the manifest says of each (`category`, `age_group`, `competition_label`) is read from the catalogue the way `competition_categories` does.
const FORMATION = [
  'CE_SSAA_Cadete_Fem_2024_2025_11º-12º_11º-12º', 'CE_SSAA_Cadete_Fem_2024_2025_15º-16º_15º-16º', 'CE_SSAA_Cadete_Fem_2024_2025_17º-18º_17º-18º', 'CE_SSAA_Cadete_Fem_2024_2025_3º-4º_3º-4º',
  'CE_SSAA_Cadete_Fem_2024_2025_7º-8º_7º-8º', 'CE_SSAA_Cadete_Fem_2024_2025_Fase_Grupos_A', 'CE_SSAA_Cadete_Fem_2024_2025_Fase_Grupos_B', 'CE_SSAA_Cadete_Fem_2024_2025_Fase_Grupos_C',
  'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_1-8_1_2_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_1-8_1_4_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_1-8_Final',
  'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_13-16_1_2_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_13-16_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_5-8_1_2_Final',
  'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_5-8_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_9-16_1_2_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_9-16_1_4_Final',
  'CE_SSAA_Cadete_Fem_2024_2025_Play-Off_9-16_Final', 'CE_SSAA_Cadete_Fem_2024_2025_Puestos_17º-19º_17º-19º', 'CE_SSAA_Cadete_Fem_2025_2026_Fase_Grupos_A',
  'CE_SSAA_Cadete_Mas_2024_2025_PRIMERA_FASE_A', 'C_ESP_CLUBES_JR_FEM_2024_2025_PRIMERA_FASE_A', 'C_ESP_CLUBES_JR_FEM_2024_2025_3º-4º_3º-4º', 'C_ESP_CLUBES_CAD_MASC_2024_2025_PRIMERA_FASE_A',
  'C_ESP_CLUBES_CAD_FEM_2024_2025_PRIMERA_FASE_A', 'C_ESP_CLUBES_JR_MASC_2024_2025_PRIMERA_FASE_A',
  'LF_ENDESA_2024_2025_Liga_Regular_Único', 'LF_ENDESA_2024_2025_Play-Offs_1_2_Final', 'LF_ENDESA_2024_2025_Play-Offs_1_4_Final', 'LF_ENDESA_2024_2025_Play-Offs_Final',
  'LF_ENDESA_2024_2025_C_SM_Reina_1_4_Final', 'LF_ENDESA_2024_2025_C_SM_Reina_1_2_Final', 'LF_ENDESA_2024_2025_C_SM_Reina_Final',
  'PRIMERA_FEB_2024_2025_Liga_Regular_Único', 'L_F_-2_2024_2025_Fase_Final_1_2_1_2_Final', 'L_F_-2_2024_2025_Fase_Final_1_4_GR_1', 'L_F_-2_2024_2025_Fase_Final_1_4_GR_2',
  'L_F_-2_2024_2025_Liga_Regular_A', 'LIGA_U_2025_2026_2ª_FASE_Grupo_A', 'LIGA_U_2025_2026_PLAY-OUT_2ºB-7ºA', 'LIGA_U_2025_2026_PLAY-OUT_6ºA-3ºB', 'LIGA_U_2025_2026_LIGA_REGULAR_GRUPO_A',
]
interface CatalogueEntry { league?: string; competition: string; category?: string; age_group?: string; label?: string }
const CATALOGUE: CatalogueEntry[] = JSON.parse(readFileSync(join(__dirname, '../../../config/competitions.json'), 'utf8')).competitions
const plain = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '')

/** What the manifest says of a collection: the facts of its competition in the catalogue (a name the catalogue does not know says nothing). */
function published(collection: string) {
  const competition = plain(collection.split('_').slice(0, collection.split('_').findIndex(p => /^\d{4}$/.test(p))).join('_'))
  const entry = CATALOGUE.find(e => (e.league ?? 'feb') === 'feb' && plain(e.competition) === competition)
  return { collection, league: 'feb' as const, games: 3, ...(entry ? { category: (entry.category ?? 'senior') as 'senior' | 'formacion', ...(entry.age_group ? { age_group: entry.age_group as 'U16' | 'U18' } : {}), ...(entry.label ? { competition_label: entry.label } : {}) } : {}) }
}
const FORMATION_LIST = collectionList(FORMATION.map(published))
const MAS = 'Selecciones autonómicas · Cadete masculino'
const FEM = 'Selecciones autonómicas · Cadete femenino'
const YOUTH_NAMES = new Set(FORMATION_LIST.filter(c => c.category === 'formacion').map(c => c.competition_label))
const groupsOf = (competition: string, season = '2024/2025') =>
  pickCollection(FORMATION_LIST, { ambito: 'FEB', category: YOUTH_NAMES.has(competition) ? 'Formación' : 'Sénior', season, competition }).groups

describe('the category of a competition in the selector (issue #914)', () => {
  it('the levels are ámbito, categoría, temporada, competición and grupo, and the category is Sénior or Formación, Sénior first', () => {
    const p = pickCollection(FORMATION_LIST, { ambito: 'FEB' })
    expect(p.categories).toEqual(['Sénior', 'Formación'])
    expect(p.selection).toMatchObject({ ambito: 'FEB', category: 'Sénior', season: '2025/2026' })
    expect(levelsOf(FORMATION_LIST.find(c => c.name.startsWith('CE_SSAA_Cadete_Fem_2024'))!).category).toBe('Formación')
    expect(levelsOf(FORMATION_LIST.find(c => c.name.startsWith('PRIMERA_FEB'))!).category).toBe('Sénior')
  })

  it('each category offers only its own seasons and competitions', () => {
    const senior = pickCollection(FORMATION_LIST, { ambito: 'FEB', category: 'Sénior', season: '2024/2025' })
    expect(senior.competitions).toEqual(['L F -2', 'LF ENDESA', 'PRIMERA FEB'])
    const youth = pickCollection(FORMATION_LIST, { ambito: 'FEB', category: 'Formación', season: '2024/2025' })
    expect(youth.competitions).toEqual(['Campeonato de España de clubes · Cadete femenino', 'Campeonato de España de clubes · Cadete masculino', 'Campeonato de España de clubes · Júnior femenino',
      'Campeonato de España de clubes · Júnior masculino', FEM, MAS])
    expect(pickCollection(FORMATION_LIST, { ambito: 'FEB', category: 'Formación' }).seasons).toEqual(['2025/2026', '2024/2025'])        // LIGA U (2025/2026) is senior: it adds nothing here
  })

  it('a category that has nothing in the season chosen falls back to its default instead of an impossible combination', () => {
    const p = pickCollection(FORMATION_LIST, { ambito: 'FEB', category: 'Formación', season: '2025/2026', competition: 'LF ENDESA' })
    expect(p.selection.category).toBe('Formación')
    expect(p.selection.competition).toBe(FEM)                                       // LF ENDESA is senior: the competition falls back
    expect(p.collection).not.toBeNull()
  })

  it('the competition is named by the label of the catalogue and, without it, as FEB writes it (never renamed by guessing)', () => {
    const names = FORMATION_LIST.filter(c => c.category === 'formacion').map(c => levelsOf(c).competition)
    expect(names.every(n => /^(Campeonato de España de clubes|Selecciones autonómicas) · /.test(n))).toBe(true)
    const list = collectionList([{ collection: 'C_ESP_CLUBES_INF_FEM_2024_2025_PRIMERA_FASE_A', league: 'feb', games: 1 }])
    expect(levelsOf(list[0]).competition).toBe('C ESP CLUBES INF FEM')
    expect(levelsOf(list[0]).category).toBe('Sénior')                              // without a category from the manifest it is senior (older publications)
  })

  it('every collection is reachable from its own levels, the category included, and the order does not depend on how they come', () => {
    for (const c of FORMATION_LIST) expect(pickCollection(FORMATION_LIST, selectionOf(c)).collection?.name).toBe(c.name)
    const reversed = pickCollection([...FORMATION_LIST].reverse(), { ambito: 'FEB', category: 'Formación', season: '2024/2025', competition: FEM }).groups
    expect(reversed).toEqual(groupsOf(FEM))
  })
})

describe('the groups and the names of the youth competitions in the selector (issue #908)', () => {
  it('the group is not repeated when the phase and the group say the same: «3º-4º», not «3º-4º 3º-4º»', () => {
    expect(groupsOf(FEM)).toEqual(expect.arrayContaining(['3º-4º', '7º-8º', '11º-12º', 'Puestos 17º-19º']))
    expect(groupsOf(FEM).filter(g => /(\S+) \1/.test(g))).toEqual([])
    expect(groupsOf('L F -2')).toContain('Fase Final 1/2 Final')                      // «Fase Final 1/2 1/2 Final» in the data: the round was written twice
  })

  it('the rounds of a draw are read as fractions («1 2» is 1/2) without touching the places they play for («1-8»)', () => {
    expect(groupsOf(FEM)).toEqual(expect.arrayContaining(['Play-Off 1-8 1/2 Final', 'Play-Off 9-16 1/4 Final', 'Play-Off 13-16 Final']))
  })

  it('the groups go: first phase, then the eliminatory rounds from the biggest draw to the final, then the classification games', () => {
    expect(groupsOf(FEM)).toEqual([
      'Fase Grupos A', 'Fase Grupos B', 'Fase Grupos C',
      'Play-Off 1-8 1/4 Final', 'Play-Off 1-8 1/2 Final', 'Play-Off 1-8 Final', 'Play-Off 5-8 1/2 Final', 'Play-Off 5-8 Final',
      'Play-Off 9-16 1/4 Final', 'Play-Off 9-16 1/2 Final', 'Play-Off 9-16 Final', 'Play-Off 13-16 1/2 Final', 'Play-Off 13-16 Final',
      '3º-4º', '7º-8º', '11º-12º', '15º-16º', '17º-18º', 'Puestos 17º-19º',
    ])
    expect(groupsOf('LF ENDESA')).toEqual(['Liga Regular', 'C SM Reina 1/4 Final', 'C SM Reina 1/2 Final', 'C SM Reina Final', 'Play-Offs 1/4 Final', 'Play-Offs 1/2 Final', 'Play-Offs Final'])
    expect(groupsOf('L F -2')).toEqual(['Liga Regular A', 'Fase Final 1/4 GR 1', 'Fase Final 1/4 GR 2', 'Fase Final 1/2 Final'])
  })

  it('a second phase goes after the first and before the eliminations, and the play-outs after the finals', () => {
    expect(groupsOf('LIGA U', '2025/2026')).toEqual(['LIGA REGULAR GRUPO A', '2ª FASE Grupo A', 'PLAY-OUT 2ºB-7ºA', 'PLAY-OUT 6ºA-3ºB'])
  })
})

// Issue #920: the FBCYL competitions of the catalogue (autonomic, cadete upwards and senior; men and women) as the selector shows them. The entries are the REAL ones of `config/competitions.json`
// and the collection names are made like `get_collection_name` does (spaces and dots become underscores).
const sanitize = (text: string) => text.trim().replace(/\s+/g, '_').replace(/[:*?"<>|.$/\\]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
interface FbcylEntry extends CatalogueEntry { season_value: string; active: boolean; group_label?: string; fbcyl: { gender: string; territory: string } }
const FBCYL_ENTRIES = (JSON.parse(readFileSync(join(__dirname, '../../../config/competitions.json'), 'utf8')).competitions as (CatalogueEntry & { league?: string })[]).filter(e => e.league === 'fbcyl') as FbcylEntry[]
const FBCYL_LIST = collectionList(FBCYL_ENTRIES.map(e => ({
  collection: `${sanitize(`FBCYL_${e.competition}`)}_${sanitize(e.season_value)}_`, league: 'fbcyl' as const, games: 3,
  ...(e.category ? { category: e.category as 'senior' | 'formacion' } : {}), ...(e.age_group ? { age_group: e.age_group as 'U16' | 'U18' } : {}),
  ...(e.label ? { competition_label: e.label } : {}), ...(e.group_label ? { group_label: e.group_label } : {}),
})))
const fbcyl = (wanted: Record<string, string>) => pickCollection(FBCYL_LIST, { ambito: 'FBCYL', ...wanted })

describe('the FBCYL competitions in the selector (issue #920)', () => {
  it('FBCYL has the same levels as FEB: the senior competitions and the youth ones (cadete and júnior) as a category of their own', () => {
    expect(fbcyl({}).categories).toEqual(['Sénior', 'Formación'])
    expect(fbcyl({ category: 'Formación' }).seasons).toEqual(['2026/2027', '2025/2026', '2024/2025'])
  })

  it('the senior ones are the two groups of the Primera Nacional Femenina that were already there and the men and the other senior women', () => {
    expect(fbcyl({ category: 'Sénior', season: '2026/2027' }).competitions).toEqual(['1ª División Femenina', '1ª División masculina', 'Sénior FBCYL femenino'])
  })

  it('cadete and júnior, men and women, with a readable name: nothing of infantil or minibásket', () => {
    const names = fbcyl({ category: 'Formación', season: '2026/2027' }).competitions
    expect(names).toEqual(['1ª División cadete femenino', '1ª División cadete masculino', '2ª División cadete femenino', '2ª División cadete masculino', '2ª División júnior femenino',
      '2ª División júnior masculino', 'Liga UEMC júnior femenino', 'Liga UEMC júnior masculino'])
    expect(names.some(n => /infantil|mini/i.test(n))).toBe(false)
  })

  it('a group is shown as the site writes it, without the code that keeps its collection name unique', () => {
    const groups = fbcyl({ category: 'Formación', season: '2026/2027', competition: 'Liga UEMC júnior femenino' }).groups
    expect(groups).toContain('LIGA UEMC JUNIOR FEM - FASE PREVIA CLASIFICACIÓN-GRUPO A')
    expect(groups.some(g => /\bG\d+$/.test(g))).toBe(false)
    expect(new Set(groups).size).toBe(groups.length)
  })

  it('the groups of the same name in different categories (the third phase, the title) are each in their own competition', () => {
    const cadete = fbcyl({ category: 'Formación', season: '2025/2026', competition: '1ª División cadete femenino' }).groups
    const junior = fbcyl({ category: 'Formación', season: '2025/2026', competition: 'Liga UEMC júnior femenino' }).groups
    expect(cadete).toContain('3ª FASE.-TITULO')                                     // the same phase in another category: each competition has its own
    expect(junior).toContain('3ª FASE. -TITULO')
  })

  it('every FBCYL collection is reachable from its own levels, and the paused seasons are listed too', () => {
    for (const c of FBCYL_LIST) expect(pickCollection(FBCYL_LIST, selectionOf(c)).collection?.name).toBe(c.name)
    expect(FBCYL_LIST.length).toBe(FBCYL_ENTRIES.length)
  })

  it('a FBCYL group the manifest says nothing of (older publications) keeps the way it was read before', () => {
    const list = collectionList([{ collection: 'FBCYL_1ª_FASE-GRUPO_A-1_2026_', league: 'fbcyl', games: 3 }])
    expect(levelsOf(list[0])).toMatchObject({ ambito: 'FBCYL', category: 'Sénior', season: '2026/2027', competition: '1ª División Femenina', group: 'FASE-GRUPO A-1' })
  })
})
