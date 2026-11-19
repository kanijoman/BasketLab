import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase } from './data'
import { AGE_VETERAN, AGE_YOUNG, HOLE_MAX_PLAYERS, MIN_ROTATION, SUGGEST_PCT, ageMix, positionBalance, profileGaps, squadOf, suggestions, teamsOf } from './myTeam'
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

describe('the holes of position', () => {
  it('count the rotation by group (bases and guards, wings, centres) with the share of minutes of each', async () => {
    const [base] = await lf2()
    const balance = positionBalance(rotation(base, ['G', 'G', 'G', 'F', 'F', 'C']))
    expect(balance.groups.map(g => [g.group, g.players])).toEqual([['G', 3], ['F', 2], ['C', 1]])
    expect(balance.groups.map(g => Math.round(g.minutesShare * 100))).toEqual([50, 33, 17])
    expect(balance.unknown).toEqual({ players: 0, minutes: 0 })
  })

  it('call a hole a group with one player of rotation or none, and only when the rotation is big enough to say it', async () => {
    const [base] = await lf2()
    expect(HOLE_MAX_PLAYERS).toBe(1)
    const holes = (groups: (PositionGroup | null)[]) => positionBalance(rotation(base, groups)).groups.filter(g => g.hole).map(g => g.group)
    expect(holes(['G', 'G', 'G', 'F', 'F', 'C'])).toEqual(['C'])
    expect(holes(['G', 'G', 'G', 'F', 'F', 'F'])).toEqual(['C'])
    expect(holes(['G', 'G', 'G', 'G', 'F', 'C', 'C'])).toEqual(['F'])
    expect(MIN_ROTATION).toBe(5)
    expect(holes(['G', 'F', 'C', 'G'])).toEqual([])                       // four players of rotation: nothing can be said yet
    expect(positionBalance(rotation(base, ['G', 'F', 'C', 'G'])).reliable).toBe(false)
  })

  it('keep the players without a position apart: they are not a group and never make a hole by being missing', async () => {
    const [base] = await lf2()
    const balance = positionBalance(rotation(base, ['G', 'G', null, null, null, 'F', 'F', 'C', 'C']))
    expect(balance.unknown).toEqual({ players: 3, minutes: 3600 })
    expect(balance.groups.filter(g => g.hole)).toEqual([])
    const allUnknown = positionBalance(rotation(base, [null, null, null, null, null, null]))
    expect(allUnknown.groups.every(g => g.players === 0)).toBe(true)
    expect(allUnknown.groups.some(g => g.hole)).toBe(false)               // nobody has a position: no group can be called empty
  })
})

describe('the holes of profile', () => {
  it('are the three axes where the rotation is weakest, by the percentile weighted by minutes, with the lowest first', async () => {
    const [base] = await lf2()
    const players = rotation(base, ['G', 'F', 'C', 'G', 'F']).map(r => as(r, { pct: { ...r.pct!, pts: 90, ast: 20, orb: 30, drb: 40, stl: 80, blk: 85, efg: 70, tov: 60 } }))
    const gaps = profileGaps(players)
    expect(gaps.map(g => g.key)).toEqual(['ast', 'orb', 'drb'])
    expect(gaps.map(g => g.mean)).toEqual([20, 30, 40])
    expect(gaps[0]).toMatchObject({ label: 'Asistencias', players: 5 })
  })

  it('weigh by minutes: the one who plays more says more', async () => {
    const [base] = await lf2()
    const [a, b, c, d, e] = rotation(base, ['G', 'F', 'C', 'G', 'F'])
    const set = (r: SearchRow, minutes: number, ast: number) => as(r, { minutes, pct: { ...r.pct!, pts: 50, orb: 50, drb: 50, stl: 50, blk: 50, efg: 50, tov: 50, ast } })
    const [gap] = profileGaps([set(a, 3000, 10), set(b, 600, 90), set(c, 600, 90), set(d, 600, 90), set(e, 600, 90)])
    expect(gap.key).toBe('ast')
    expect(gap.mean).toBeCloseTo((3000 * 10 + 4 * 600 * 90) / (3000 + 4 * 600), 1)
  })

  it('leave an axis out when fewer than three of the rotation have it (never a mean of nothing), and give none for a tiny rotation', async () => {
    const [base] = await lf2()
    const players = rotation(base, ['G', 'F', 'C', 'G', 'F']).map((r, i) => as(r, { pct: { ...r.pct!, pts: 50, ast: i < 2 ? 10 : null, orb: 60, drb: 60, stl: 60, blk: 60, efg: 60, tov: 60 } }))
    expect(profileGaps(players).map(g => g.key)).not.toContain('ast')
    expect(profileGaps(rotation(base, ['G', 'F', 'C', 'G']))).toEqual([])
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
  it('for a hole of position asks for that group, with minutes enough, in the season of the team', async () => {
    const [base] = await lf2()
    const out = suggestions({ season: '2025', balance: positionBalance(rotation(base, ['G', 'G', 'G', 'F', 'F', 'C'])), gaps: [] })
    expect(out).toHaveLength(1)
    const url = new URL(out[0].href, 'https://x.test')
    expect(url.pathname).toBe('/')
    expect(url.searchParams.get('s')).toBe('2025')
    expect(filtersFromParams(url.searchParams)).toMatchObject({ groups: ['C'], onlyEligible: true, metric: '', pctMin: null })
  })

  it('for a weak axis asks for a percentile of 75 or more in it, with minutes enough', async () => {
    const [base] = await lf2()
    expect(SUGGEST_PCT).toBe(75)
    const balance = positionBalance(rotation(base, ['G', 'G', 'F', 'F', 'C', 'C']))
    const out = suggestions({ season: '2025', balance, gaps: [{ key: 'ast', label: 'Asistencias', short: 'Ast', mean: 20, players: 5 }] })
    expect(out).toHaveLength(1)
    expect(filtersFromParams(new URL(out[0].href, 'https://x.test').searchParams)).toMatchObject({ metric: 'ast', pctMin: 75, onlyEligible: true, groups: [] })
    expect(out[0].label).toMatch(/asistencias/i)
  })

  it('is nothing when there are no holes', async () => {
    const [base] = await lf2()
    expect(suggestions({ season: '2025', balance: positionBalance(rotation(base, ['G', 'G', 'F', 'F', 'C', 'C'])), gaps: [] })).toEqual([])
  })
})
