import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase, type TalentCompetitionEntry, type TalentRow } from './data'
import {
  ageOn1231, applySearch, csvOf, defaultSearch, filtersFromParams, filtersToParams, mixNotice, NO_FILTERS, MAX_AUTO_COMPETITIONS, type SearchFilters, type SearchRow,
} from './search'
import { FBCYL_KEY, LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The search of Talent (B3, #879) over the REAL publication of the exporter: FEB LF2 2025 with bio and FBCYL 2026 without it. */
let lf2: SearchRow[]
let fbcyl: SearchRow[]
let entries: TalentCompetitionEntry[]

const asRows = (key: string, entry: TalentCompetitionEntry, rows: TalentRow[]): SearchRow[] =>
  rows.map(r => ({ ...r, comp_key: key, competition: entry.competition, season: entry.season, season_label: entry.season_label, gender: entry.gender, level: entry.level, age: ageOn1231(r.birth, entry.season) }))

beforeEach(async () => {
  localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData()
  entries = await loadTalentCompetitions()
  lf2 = asRows(LF2_KEY, entries.find(e => e.key === LF2_KEY)!, (await loadCompetitionRows(LF2_KEY)).rows)
  fbcyl = asRows(FBCYL_KEY, entries.find(e => e.key === FBCYL_KEY)!, (await loadCompetitionRows(FBCYL_KEY)).rows)
})

const f = (over: Partial<SearchFilters> = {}): SearchFilters => ({ ...NO_FILTERS, ...over })

describe('the age is the one of 31/12 of the year the season starts in', () => {
  it.each([
    ['2004-05-06', '2025', 21], ['2004-12-31', '2025', 21], ['2005-01-01', '2025', 20], ['2004-05-06', '2026', 22], ['1990-02-29', '2025', 35],
  ])('born %s in season %s is %i', (birth, season, age) => expect(ageOn1231(birth, season)).toBe(age))

  it.each([[null, '2025'], ['', '2025'], ['no es una fecha', '2025'], ['2004-05-06', ''], ['2004-05-06', 'x'], ['0000-01-01', '2025'], ['2040-01-01', '2025']])('%s in %s is not known (None, not 0)', (birth, season) =>
    expect(ageOn1231(birth as string | null, season)).toBeNull())
})

describe('the filters over real rows', () => {
  it('no filter keeps every row of every competition, in the order they came', () => {
    const { rows } = applySearch([...lf2, ...fbcyl], f())
    expect(rows.map(r => r.person_id + r.team_id)).toEqual([...lf2, ...fbcyl].map(r => r.person_id + r.team_id))
  })

  it('the age and the height are inclusive limits and a row that does not say them is hidden, not read as 0', () => {
    const ana = lf2.find(r => r.person_id === 'feb:10100')!
    expect(ana.age).toBe(21)
    expect(applySearch(lf2, f({ ageMin: 21, ageMax: 21 })).rows.map(r => r.person_id)).toContain('feb:10100')
    expect(applySearch(lf2, f({ ageMin: 22 })).rows.map(r => r.person_id)).not.toContain('feb:10100')
    expect(applySearch(lf2, f({ heightMin: 178, heightMax: 178 })).rows.map(r => r.person_id)).toContain('feb:10100')
    expect(applySearch(lf2, f({ heightMax: 177 })).rows.map(r => r.person_id)).not.toContain('feb:10100')
    expect(applySearch(fbcyl, f({ ageMin: 0 })).rows).toEqual([])                        // FBCYL has no bio: age 0 is a real filter, «no data» is not a 0
    expect(applySearch(fbcyl, f({ heightMin: 100 })).rows).toEqual([])
  })

  it('«include those without data» brings them back and the count of the hidden ones says how many are missing in each field', () => {
    const strict = applySearch(fbcyl, f({ ageMin: 18, heightMin: 150 }))
    expect(strict.rows).toEqual([])
    expect(strict.hidden).toEqual({ age: fbcyl.length, height: fbcyl.length, position: 0, metric: 0, total: fbcyl.length })
    const lenient = applySearch(fbcyl, f({ ageMin: 18, heightMin: 150, includeUnknown: true }))
    expect(lenient.rows).toHaveLength(fbcyl.length)
    expect(lenient.hidden.total).toBe(0)
  })

  it('a row that fails a known value is not «hidden for lack of data» even if another field is also missing', () => {
    const young = { ...lf2[0], age: 15, height: null }
    const out = applySearch([young], f({ ageMin: 18, heightMin: 170 }))
    expect(out.rows).toEqual([])
    expect(out.hidden.total).toBe(0)
    expect(applySearch([young], f({ ageMin: 18, heightMin: 170, includeUnknown: true })).rows).toEqual([])      // age is known and too low: no switch brings it back
  })

  it('the position is the group G, F or C (what every source can say) and several groups add up', () => {
    const base = { ...lf2[0], position: 'Base', position_group: 'G' as const }
    const alero = { ...lf2[0], person_id: 'x', position: 'Alero', position_group: 'F' as const }
    const only = { ...lf2[0], person_id: 'y', position: null, position_group: null }
    expect(applySearch([base, alero, only], f({ groups: ['G'] })).rows).toEqual([base])
    expect(applySearch([base, alero, only], f({ groups: ['G', 'F'] })).rows).toEqual([base, alero])
    const hidden = applySearch([base, alero, only], f({ groups: ['C'] }))
    expect(hidden.rows).toEqual([])
    expect(hidden.hidden.position).toBe(1)
    expect(applySearch([base, alero, only], f({ groups: ['C'], includeUnknown: true })).rows).toEqual([only])
  })

  it('the percentile is the one of the player in his own competition and one without it (too few minutes) is «no data»', () => {
    const rows = lf2.filter(r => r.pct)
    expect(rows.length).toBeGreaterThan(0)
    const best = applySearch(lf2, f({ metric: 'pts', pctMin: 50 })).rows
    expect(best.every(r => (r.pct?.pts ?? -1) >= 50)).toBe(true)
    const none = applySearch([{ ...lf2[0], pct: null }], f({ metric: 'pts', pctMin: 1 }))
    expect(none.rows).toEqual([])
    expect(none.hidden.metric).toBe(1)
  })

  it('eligible only keeps those with enough minutes and the text finds the player by name, full name or team without accents or case', () => {
    expect(applySearch(lf2, f({ onlyEligible: true })).rows.every(r => r.eligible)).toBe(true)
    const ana = lf2.find(r => r.person_id === 'feb:10100')!
    expect(applySearch(lf2, f({ text: 'ana prueba' })).rows.map(r => r.person_id)).toContain('feb:10100')
    expect(applySearch(lf2, f({ text: 'ANA  PRUEBA' })).rows.map(r => r.person_id)).toContain('feb:10100')
    expect(applySearch(lf2, f({ text: ana.team_name.slice(0, 4).toUpperCase() })).rows.length).toBeGreaterThan(0)
    expect(applySearch(lf2, f({ text: 'zzzz no existe' })).rows).toEqual([])
    const maria = { ...lf2[0], name: 'M. NÚÑEZ', full_name: 'MARÍA NÚÑEZ PÉREZ' }
    expect(applySearch([maria], f({ text: 'maria nunez' })).rows).toEqual([maria])
    expect(applySearch([maria], f({ text: 'María Núñez' })).rows).toEqual([maria])
  })

  it('does not change the rows it receives and gives the same result twice', () => {
    const copy = JSON.parse(JSON.stringify(lf2))
    const a = applySearch(lf2, f({ ageMin: 18, groups: ['G'] }))
    expect(lf2).toEqual(copy)
    expect(applySearch(lf2, f({ ageMin: 18, groups: ['G'] }))).toEqual(a)
  })

  it('nothing to search is nothing found', () => {
    expect(applySearch([], f({ ageMin: 18 }))).toEqual({ rows: [], hidden: { age: 0, height: 0, position: 0, metric: 0, total: 0 } })
  })
})

describe('mixing competitions is allowed and warned', () => {
  it('says nothing for the same federation, level and gender', () => {
    const lf2Entry = entries.find(e => e.key === LF2_KEY)!
    expect(mixNotice([lf2Entry])).toBeNull()
    expect(mixNotice([])).toBeNull()
    expect(mixNotice([lf2Entry, { ...lf2Entry, key: 'otra' }])).toBeNull()
  })

  it('warns that the percentiles belong to each competition when the gender, the level or the federation differ', () => {
    const lf2Entry = entries.find(e => e.key === LF2_KEY)!
    const fbcylEntry = entries.find(e => e.key === FBCYL_KEY)!
    expect(mixNotice([lf2Entry, fbcylEntry])).toMatch(/percentiles.*su competición/i)
    expect(mixNotice([lf2Entry, { ...lf2Entry, key: 'm', gender: 'M' }])).not.toBeNull()
    expect(mixNotice([lf2Entry, { ...lf2Entry, key: 'n', level: 1 }])).not.toBeNull()
  })
})

describe('where the search starts', () => {
  it('on the latest season with every competition of it', () => {
    const start = defaultSearch(entries)
    const latest = Math.max(...entries.map(e => Number(e.season)))
    expect(start.season).toBe(String(latest))
    expect(start.keys.sort()).toEqual(entries.filter(e => Number(e.season) === latest).map(e => e.key).sort())
  })

  it('with nothing published there is no season and no competition, and with too many competitions none is chosen for you', () => {
    expect(defaultSearch([])).toEqual({ season: '', keys: [] })
    const many = Array.from({ length: MAX_AUTO_COMPETITIONS + 1 }, (_, i) => ({ ...entries[0], key: `k${i}`, season: '2030' }))
    expect(defaultSearch(many)).toEqual({ season: '2030', keys: [] })
  })
})

describe('the filters live in the address, so a search is shared with a link', () => {
  it('round-trips every filter', () => {
    const all = f({ ageMin: 18, ageMax: 23, heightMin: 190, heightMax: 205, groups: ['G', 'C'], metric: 'ast', pctMin: 70, onlyEligible: true, includeUnknown: true, text: 'ana' })
    expect(filtersFromParams(filtersToParams(all))).toEqual(all)
    expect(filtersToParams(f()).toString()).toBe('')
  })

  it('ignores what it does not understand instead of failing', () => {
    const p = new URLSearchParams('amin=abc&amax=-3&hmin=&pos=G,X,C&m=nope&p=500&u=maybe')
    expect(filtersFromParams(p)).toEqual(f({ groups: ['G', 'C'] }))
  })
})

describe('the CSV of the result', () => {
  it('has a header, a row per player and an empty cell where there is no data (never 0)', () => {
    const { headers, data } = csvOf([...lf2.slice(0, 1), ...fbcyl.slice(0, 1)])
    expect(headers.map(h => h.label)).toEqual(expect.arrayContaining(['Jugador', 'Equipo', 'Competición', 'Temporada', 'Edad (31/12)', 'Altura (cm)', 'Posición']))
    expect(data).toHaveLength(2)
    expect(data[1]['age']).toBeNull()
    expect(data[1]['height']).toBeNull()
  })
})
