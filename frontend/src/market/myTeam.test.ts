import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase } from './data'
import { AGE_VETERAN, AGE_YOUNG, COVER_PCT, MIN_ROTATION, SUGGEST_PCT, ageMix, axisCoverage, positionBalance, squadOf, suggestions, teamsOf } from './myTeam'
import { filtersFromParams } from './search'
import { toSearchRow, type PositionGroup, type SearchRow } from './search'
import { LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** «Mi equipo» (#882) over the REAL rows of LF2 2025: the squad of a team, its rotation (who played enough), where it has holes and the search that would fill each one. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

async function lf2(): Promise<SearchRow[]> {
  const entry = (await loadTalentCompetitions()).find(e => e.key === LF2_KEY)!
  return (await loadCompetitionRows(LF2_KEY)).rows.map(r => toSearchRow(entry, r))
}

const as = (row: SearchRow, over: Partial<SearchRow>): SearchRow => ({ ...row, ...over })
const group = (g: PositionGroup | null) => ({ position_group: g, position: null })
/** A rotation of ``groups.length`` players of the same team, each with the minutes and the group asked for. */
const rotation = (base: SearchRow, groups: (PositionGroup | null)[], minutes = 1200): SearchRow[] =>
  groups.map((g, i) => as(base, { person_id: `feb:r${i}`, name: `R${i}`, full_name: null, minutes, eligible: true, ...group(g) }))

describe('the teams and the squad', () => {
  it('lists the teams of a competition once each, by name, with how many players they have', async () => {
    const rows = await lf2()
    const teams = teamsOf(rows)
    expect(teams.length).toBeGreaterThan(1)
    expect(new Set(teams.map(t => t.team_id)).size).toBe(teams.length)
    expect(teams.map(t => t.team_name)).toEqual([...teams.map(t => t.team_name)].sort((a, b) => a.localeCompare(b)))
    expect(teams.reduce((n, t) => n + t.players, 0)).toBe(rows.length)
  })

  it('is the rows of that team in that competition, the rotation (who played enough) first and by minutes, the rest as the bench', async () => {
    const rows = await lf2()
    const team = teamsOf(rows)[0]
    const squad = squadOf(rows, LF2_KEY, team.team_id)
    expect([...squad.rotation, ...squad.bench].every(r => r.team_id === team.team_id && r.comp_key === LF2_KEY)).toBe(true)
    expect(squad.rotation.every(r => r.eligible) && squad.bench.every(r => !r.eligible)).toBe(true)
    const minutes = squad.rotation.map(r => r.minutes)
    expect([...minutes].sort((a, b) => b - a)).toEqual(minutes)
  })

  it('does not depend on the order of the rows, and gives nothing for a team that is not there', async () => {
    const rows = await lf2()
    const team = teamsOf(rows)[0]
    expect(squadOf([...rows].reverse(), LF2_KEY, team.team_id)).toEqual(squadOf(rows, LF2_KEY, team.team_id))
    expect(squadOf(rows, LF2_KEY, 'nadie')).toEqual({ rotation: [], bench: [] })
  })
})

describe('the position of the rotation (information, not a hole)', () => {
  it('counts the rotation by group (bases and guards, wings, centres) with the share of minutes of each', async () => {
    const [base] = await lf2()
    const balance = positionBalance(rotation(base, ['G', 'G', 'G', 'F', 'F', 'C']))
    expect(balance.groups.map(g => [g.group, g.players])).toEqual([['G', 3], ['F', 2], ['C', 1]])
    expect(balance.groups.map(g => Math.round(g.minutesShare * 100))).toEqual([50, 33, 17])
    expect(balance.unknown).toEqual({ players: 0, minutes: 0 })
  })

  it('keeps the players without a position apart: they are not a group', async () => {
    const [base] = await lf2()
    const balance = positionBalance(rotation(base, ['G', 'G', null, null, null, 'F', 'F', 'C', 'C']))
    expect(balance.unknown).toEqual({ players: 3, minutes: 3600 })
    expect(positionBalance(rotation(base, [null, null])).groups.every(g => g.players === 0 && g.minutesShare === 0)).toBe(true)
  })
})

/** A rotation of six where each player has the percentile asked for on each axis (the rest at 50). */
const withPcts = (base: SearchRow, each: Record<string, number | null>[]): SearchRow[] =>
  rotation(base, each.map(() => 'C' as PositionGroup)).map((r, i) => as(r, { person_id: `feb:p${i}`, name: `P${i}`, pct: { ...r.pct!, pts: 50, ast: 50, orb: 50, drb: 50, stl: 50, blk: 50, efg: 50, tov: 50, ...each[i] } }))

describe('the holes of profile: an axis that NOBODY in the rotation covers', () => {
  it('is a hole when the best of the rotation does not reach the percentile 75, even with three centres: what matters is the game they give, not their position', async () => {
    const [base] = await lf2()
    expect(COVER_PCT).toBe(75)
    const six = withPcts(base, [{ orb: 40, drb: 60 }, { orb: 55, drb: 65 }, { orb: 62, drb: 70 }, { orb: 30 }, { orb: 20 }, { orb: 10 }])
    const cover = axisCoverage(six)
    const reb = cover.find(c => c.key === 'reb')!
    expect(reb).toMatchObject({ hole: true, bestPct: 66, players: 6, label: 'Rebotes' })          // a player rebounds as the mean of his offensive and defensive percentiles: (62 + 70) / 2
    expect(reb.best?.person_id).toBe('feb:p2')
    expect(cover.map(c => c.key)).not.toContain('orb')
    expect(cover.map(c => c.key)).not.toContain('drb')                                          // one axis for rebounds, not two
  })

  it('is covered with one player at 75 or more, however weak the rest are (a mean would hide him)', async () => {
    const [base] = await lf2()
    const six = withPcts(base, [{ orb: 80, drb: 70 }, { orb: 5, drb: 5 }, { orb: 5, drb: 5 }, { orb: 5, drb: 5 }, { orb: 5, drb: 5 }, { orb: 5, drb: 5 }])
    expect(axisCoverage(six).find(c => c.key === 'reb')).toMatchObject({ hole: false, bestPct: 75 })
    expect(axisCoverage(withPcts(base, [{ orb: 80, drb: 69.8 }, { orb: 5 }, { orb: 5 }, { orb: 5 }, { orb: 5 }, { orb: 5 }])).find(c => c.key === 'reb')!.hole).toBe(true)
  })

  it('says every axis in the order of the radar (rebounds as one), and the best player of each', async () => {
    const [base] = await lf2()
    const cover = axisCoverage(withPcts(base, Array.from({ length: 6 }, () => ({}))))
    expect(cover.map(c => c.key)).toEqual(['pts', 'ast', 'reb', 'stl', 'blk', 'efg', 'tov'])
    expect(cover.every(c => c.best !== null && c.bestPct === 50)).toBe(true)
  })

  it('does not call a hole an axis for which fewer than three of the rotation have a figure, nor anything for a rotation too small', async () => {
    const [base] = await lf2()
    const sparse = withPcts(base, [{ orb: 10 }, { orb: 10 }, { orb: null }, { orb: null }, { orb: null }, { orb: null }])
    expect(axisCoverage(sparse).find(c => c.key === 'reb')).toMatchObject({ hole: false, players: 2 })          // rebounds need both his figures
    expect(MIN_ROTATION).toBe(5)
    const small = withPcts(base, [{ orb: 10 }, { orb: 10 }, { orb: 10 }, { orb: 10 }])
    expect(axisCoverage(small).every(c => !c.hole)).toBe(true)
  })

  it('leaves out an axis nobody has, with no best player, never a zero', async () => {
    const [base] = await lf2()
    const none = withPcts(base, Array.from({ length: 6 }, () => ({ blk: null })))
    expect(axisCoverage(none).find(c => c.key === 'blk')).toMatchObject({ best: null, bestPct: null, players: 0, hole: false })
  })

  it('breaks a tie of the best by minutes, then by name, so the order of the rows does not matter', async () => {
    const [base] = await lf2()
    const six = withPcts(base, [{ ast: 80 }, { ast: 80 }, { ast: 10 }, { ast: 10 }, { ast: 10 }, { ast: 10 }]).map((r, i) => as(r, { minutes: 1000 + (i === 1 ? 500 : 0) }))
    expect(axisCoverage(six).find(c => c.key === 'ast')!.best?.person_id).toBe('feb:p1')
    expect(axisCoverage([...six].reverse())).toEqual(axisCoverage(six))
  })
})

describe('the age of the rotation', () => {
  it('is the share of the minutes of the young (under 22) and the veterans (30 or more) among those whose age is known, and says how much is not known', async () => {
    const [base] = await lf2()
    expect([AGE_YOUNG, AGE_VETERAN]).toEqual([22, 30])
    const ages = [19, 21, 22, 29, 30, null].map((age, i) => as(rotation(base, ['G'])[0], { person_id: `feb:a${i}`, age, minutes: 600 }))
    const mix = ageMix(ages)
    expect(mix.young).toBeCloseTo(2 / 5)
    expect(mix.veteran).toBeCloseTo(1 / 5)
    expect(mix.unknown).toBeCloseTo(1 / 6)
  })

  it('is empty, not zero, when nobody has an age', async () => {
    const [base] = await lf2()
    expect(ageMix(rotation(base, ['G', 'F']).map(r => as(r, { age: null }))).young).toBeNull()
  })
})

describe('the search that would fill a hole', () => {
  it('asks for a percentile of 75 or more in the axis nobody covers, with minutes enough, in the season of the team', async () => {
    const [base] = await lf2()
    expect(SUGGEST_PCT).toBe(75)
    const six = withPcts(base, Array.from({ length: 6 }, () => ({ ast: 20 })))
    const out = suggestions({ season: '2025', coverage: axisCoverage(six) })
    const ast = out.find(s => s.key === 'axis-ast')!
    const url = new URL(ast.href, 'https://x.test')
    expect(url.pathname).toBe('/')
    expect(url.searchParams.get('s')).toBe('2025')
    expect(filtersFromParams(url.searchParams)).toMatchObject({ metric: 'ast', pctMin: 75, onlyEligible: true, groups: [] })
    expect(ast.label).toMatch(/asistencias/i)
  })

  it('for rebounds asks for the one of the two (offensive or defensive) where the rotation is weakest, and says which', async () => {
    const [base] = await lf2()
    const weakOffence = withPcts(base, [{ orb: 20, drb: 70 }, { orb: 30, drb: 72 }, { orb: 10, drb: 60 }, { orb: 10 }, { orb: 10 }, { orb: 10 }])
    const [off] = suggestions({ season: '2025', coverage: axisCoverage(weakOffence) }).filter(s => s.key === 'axis-reb')
    expect(filtersFromParams(new URL(off.href, 'https://x.test').searchParams)).toMatchObject({ metric: 'orb', pctMin: 75 })
    expect(off.label).toMatch(/rebotes ofensivos/i)
    const weakDefence = withPcts(base, [{ orb: 70, drb: 20 }, { orb: 72, drb: 30 }, { orb: 60, drb: 10 }, { drb: 10 }, { drb: 10 }, { drb: 10 }])
    const [def] = suggestions({ season: '2025', coverage: axisCoverage(weakDefence) }).filter(s => s.key === 'axis-reb')
    expect(filtersFromParams(new URL(def.href, 'https://x.test').searchParams)).toMatchObject({ metric: 'drb' })
    expect(def.label).toMatch(/rebotes defensivos/i)
  })

  it('puts the biggest hole first (the one whose best player is furthest from 75) and is nothing when everything is covered', async () => {
    const [base] = await lf2()
    const six = withPcts(base, [{ orb: 70, drb: 70, ast: 20 }, { orb: 60, drb: 60, ast: 30 }, { orb: 50, ast: 10 }, { orb: 50, ast: 5 }, { orb: 50, ast: 5 }, { orb: 50, ast: 5 }])
    const keys = suggestions({ season: '2025', coverage: axisCoverage(six) }).map(s => s.key)
    expect(keys.indexOf('axis-ast')).toBeLessThan(keys.indexOf('axis-reb'))
    const covered = withPcts(base, Array.from({ length: 6 }, () => ({ pts: 90, ast: 90, orb: 90, drb: 90, stl: 90, blk: 90, efg: 90, tov: 90 })))
    expect(suggestions({ season: '2025', coverage: axisCoverage(covered) })).toEqual([])
  })
})
