import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase } from './data'
import { fitIn, SUBSTITUTE_SIMILARITY } from './fit'
import { COVER_PCT, MIN_ROTATION, axisCoverage, squadOf, teamsOf } from './myTeam'
import { toSearchRow, type SearchRow } from './search'
import { LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The fit of a player with a squad (#883): what he adds to the holes of the rotation, where he collides with who is already good at it and whom he would replace, over rows of LF2 2025. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

async function lf2(): Promise<SearchRow[]> {
  const entry = (await loadTalentCompetitions()).find(e => e.key === LF2_KEY)!
  return (await loadCompetitionRows(LF2_KEY)).rows.map(r => toSearchRow(entry, r))
}

type Pct = NonNullable<SearchRow['pct']>
const FLAT = { pts: 50, ast: 50, orb: 50, drb: 50, stl: 50, blk: 50, efg: 50, tov: 50 } as Pct
const player = (base: SearchRow, id: string, pct: Partial<Pct>, over: Partial<SearchRow> = {}): SearchRow =>
  ({ ...base, person_id: id, name: id, full_name: null, minutes: 1200, eligible: true, linked_to: null, pct: { ...FLAT, ...pct }, ...over })
/** A rotation of six players at 50 in everything: one scores, one assists, one defends, one shoots and cares for the ball; nobody rebounds (the hole). */
const squad = (base: SearchRow): SearchRow[] => [
  player(base, 'feb:a', { pts: 90 }), player(base, 'feb:b', { ast: 80 }), player(base, 'feb:c', { stl: 78, blk: 76 }),
  player(base, 'feb:d', { efg: 80, tov: 82 }), player(base, 'feb:e', {}), player(base, 'feb:f', {}),
]
/** Far from everybody in the squad (nobody is within the similarity of a substitute). */
const ODD: Partial<Pct> = { pts: 5, ast: 99, orb: 5, drb: 5, stl: 5, blk: 99, efg: 5, tov: 5 }

describe('what a player adds to a squad', () => {
  it('complements the squad when he is good where nobody on the rotation is: the hole he fills', async () => {
    const [base] = await lf2()
    const fit = fitIn(squad(base), player(base, 'feb:new', { orb: 90, drb: 88 }))
    expect(fit.reason).toBeNull()
    expect(fit.verdict).toBe('complements')
    expect(fit.fills.map(a => a.key)).toEqual(['reb'])
  })

  it('collides when everything he does well is already covered by someone on the rotation, and says by whom', async () => {
    const [base] = await lf2()
    const fit = fitIn(squad(base), player(base, 'feb:new', { pts: 88 }))
    expect(fit.verdict).toBe('collides')
    expect(fit.fills).toEqual([])
    expect(fit.collides.map(c => [c.axis.key, c.by.person_id])).toEqual([['pts', 'feb:a']])
  })

  it('is neutral when he stands out in nothing: neither fills a hole nor collides', async () => {
    const [base] = await lf2()
    const fit = fitIn(squad(base), player(base, 'feb:new', {}))
    expect(fit.verdict).toBe('neutral')
    expect(fit.fills).toEqual([])
    expect(fit.collides).toEqual([])
  })

  it('counts the boundary as covered: exactly the cover percentile fills the hole, one point less does not', async () => {
    const [base] = await lf2()
    const at = fitIn(squad(base), player(base, 'feb:new', { orb: COVER_PCT, drb: COVER_PCT }))
    const below = fitIn(squad(base), player(base, 'feb:new', { orb: COVER_PCT - 1, drb: COVER_PCT - 1 }))
    expect(at.fills.map(a => a.key)).toEqual(['reb'])
    expect(below.verdict).toBe('neutral')
  })

  it('judges rebounds as one axis: a rebounder who is good only on the offensive glass does not fill the hole', async () => {
    const [base] = await lf2()
    expect(fitIn(squad(base), player(base, 'feb:new', { orb: 99, drb: 40 })).fills).toEqual([])
  })
})

describe('whom he would replace and the squad that results', () => {
  it('is the substitute of the rotation player whose profile is closest, when it is close enough, and not otherwise', async () => {
    const [base] = await lf2()
    const near = fitIn(squad(base), player(base, 'feb:new', { pts: 88 }))
    expect(near.substitute?.row.person_id).toBe('feb:a')
    expect(near.substitute!.similarity).toBeGreaterThanOrEqual(SUBSTITUTE_SIMILARITY)
    expect(fitIn(squad(base), player(base, 'feb:new', ODD)).substitute).toBeNull()
  })

  it('simulates the rotation with him in the place of his substitute: the holes before and after', async () => {
    const [base] = await lf2()
    const fit = fitIn(squad(base), player(base, 'feb:new', { pts: 90, orb: COVER_PCT + 1, drb: COVER_PCT + 1 }))
    expect(fit.replaced?.person_id).toBe('feb:a')
    expect(fit.holesBefore).toEqual(['reb'])
    expect(fit.holesAfter).toEqual([])
    expect(fit.opens).toEqual([])
  })

  it('warns of the hole that opens when the one he replaces was the only one who covered an axis', async () => {
    const [base] = await lf2()
    const fit = fitIn(squad(base), player(base, 'feb:new', { pts: COVER_PCT - 3 }))      // the closest is the scorer, and he is just short of covering the scoring
    expect(fit.replaced?.person_id).toBe('feb:a')
    expect(fit.opens).toEqual(['pts'])
    expect(fit.holesAfter).toEqual(['pts', 'reb'])
  })

  it('adds him on top when nobody is close: the simulated rotation has one more player', async () => {
    const [base] = await lf2()
    const fit = fitIn(squad(base), player(base, 'feb:new', ODD))
    expect(fit.replaced).toBeNull()
    expect(fit.after.every(a => a.players === 7)).toBe(true)
    expect(fit.holesAfter).toEqual(fit.holesBefore)
  })
})

describe('when it cannot be said', () => {
  it('says why: few minutes, no profile, a rotation too small, or he is already in the team', async () => {
    const [base] = await lf2()
    expect(fitIn(squad(base), player(base, 'feb:new', { orb: 90 }, { eligible: false })).reason).toBe('few-minutes')
    expect(fitIn(squad(base), { ...player(base, 'feb:new', {}), pct: null }).reason).toBe('no-profile')
    expect(fitIn(squad(base).slice(0, MIN_ROTATION - 1), player(base, 'feb:new', { orb: 90 })).reason).toBe('small-rotation')
    expect(fitIn(squad(base), squad(base)[0]).reason).toBe('in-team')
    expect(fitIn(squad(base), player(base, 'fbcyl:x', { orb: 90 }, { linked_to: 'feb:a' })).reason).toBe('in-team')
  })

  it('does not depend on the order of the rows of the rotation', async () => {
    const [base] = await lf2()
    const candidate = player(base, 'feb:new', { pts: 90, orb: 90, drb: 90 })
    expect(fitIn([...squad(base)].reverse(), candidate)).toEqual(fitIn(squad(base), candidate))
  })

  it('works with a real squad of the competition: the rotation of a team and a player of another one', async () => {
    const rows = await lf2()
    const [one, other] = teamsOf(rows).filter(t => squadOf(rows, LF2_KEY, t.team_id).rotation.length >= MIN_ROTATION)
    const rotation = squadOf(rows, LF2_KEY, one.team_id).rotation
    const candidate = squadOf(rows, LF2_KEY, other.team_id).rotation.find(r => r.pct)!
    const fit = fitIn(rotation, candidate)
    expect(fit.reason).toBeNull()
    expect(fit.holesBefore).toEqual(axisCoverage(rotation).filter(a => a.hole).map(a => a.key))
  })
})
