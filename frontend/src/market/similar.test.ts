import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase } from './data'
import { MIN_SHARED_AXES, SIMILAR_LIMIT, similarPlayers } from './similar'
import { RADAR_AXES } from './player'
import { toSearchRow, type SearchRow } from './search'
import { LF2_KEY, serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The players like him (#1010) over the REAL rows of LF2 2025: how close their percentiles on the eight axes are, inside his own competition and season, and never mixing competitions. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

async function lf2(): Promise<SearchRow[]> {
  const entry = (await loadTalentCompetitions()).find(e => e.key === LF2_KEY)!
  return (await loadCompetitionRows(LF2_KEY)).rows.map(r => toSearchRow(entry, r))
}

const withPct = (row: SearchRow, over: Record<string, number | null>, extra: Partial<SearchRow> = {}): SearchRow =>
  ({ ...row, ...extra, pct: { ...row.pct!, ...over } })

describe('the players like him', () => {
  it('are the five closest in percentiles, the most alike first, with a similarity of 0 to 100 and never himself', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    const { similar, reason } = similarPlayers(rows, target)
    expect(reason).toBeNull()
    expect(similar).toHaveLength(SIMILAR_LIMIT)
    expect(similar.every(s => s.row.person_id !== target.person_id)).toBe(true)
    const sims = similar.map(s => s.similarity)
    expect([...sims].sort((a, b) => b - a)).toEqual(sims)
    expect(sims.every(s => s >= 0 && s <= 100)).toBe(true)
  })

  it('give 100 for the same profile and fall as the percentiles move apart, in points of percentile (the mean gap of the axes)', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    const twin = withPct(target, {}, { person_id: 'feb:twin', name: 'GEMELO' })
    const shifted = withPct(target, Object.fromEntries(RADAR_AXES.map(a => [a.key, Math.min(100, (target.pct![a.key] ?? 0) + 10)])), { person_id: 'feb:shift', name: 'DESPLAZADO' })
    const { similar } = similarPlayers([target, twin, shifted], target)
    expect(similar[0]).toMatchObject({ similarity: 100 })
    expect(similar[0].row.person_id).toBe('feb:twin')
    expect(similar[1].similarity).toBeGreaterThan(85)
    expect(similar[1].similarity).toBeLessThan(100)
  })

  it('only compare the axes both have, and want at least six of the eight in common (never a zero for a missing one)', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    const keys = RADAR_AXES.map(a => a.key)
    const gaps = (n: number) => Object.fromEntries(keys.slice(0, n).map(k => [k, null]))
    const six = withPct(target, gaps(2), { person_id: 'feb:six', name: 'SEIS' })           // 6 left in common
    const five = withPct(target, gaps(3), { person_id: 'feb:five', name: 'CINCO' })         // 5 left: out
    const { similar } = similarPlayers([target, six, five], target)
    expect(similar.map(s => s.row.person_id)).toContain('feb:six')
    expect(similar.map(s => s.row.person_id)).not.toContain('feb:five')
    expect(MIN_SHARED_AXES).toBe(6)
    expect(similar.find(s => s.row.person_id === 'feb:six')!.axes).toBe(6)
  })

  it('leave out whoever did not play enough, and say there are none for a player who did not play enough himself', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    const few = withPct(target, {}, { person_id: 'feb:few', name: 'POCOS', eligible: false })
    expect(similarPlayers([target, few], target).similar).toEqual([])
    const small = withPct(target, {}, { eligible: false })
    expect(similarPlayers(rows, small)).toEqual({ similar: [], reason: 'few-minutes' })
  })

  it('never mix competitions: only the rows of his own competition and season count', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    const other = withPct(target, {}, { person_id: 'feb:other', name: 'OTRA', comp_key: 'feb|otra|2025' })
    expect(similarPlayers([target, other], target).similar).toEqual([])
    expect(similarPlayers([target, { ...other, comp_key: target.comp_key }], target).similar).toHaveLength(1)
  })

  it('count a player once even if he has two rows (a transfer), with the one that resembles most, and never the same person as the target', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    const near = withPct(target, {}, { person_id: 'feb:two', name: 'DOS FILAS', team_id: 'X' })
    const far = withPct(target, Object.fromEntries(RADAR_AXES.map(a => [a.key, 0])), { person_id: 'feb:two', name: 'DOS FILAS', team_id: 'Y' })
    const mine = withPct(target, {}, { team_id: 'Z' })                                       // another row of the target himself
    const { similar } = similarPlayers([target, mine, near, far], target)
    expect(similar.filter(s => s.row.person_id === 'feb:two')).toHaveLength(1)
    expect(similar[0].similarity).toBe(100)
    expect(similar.some(s => s.row.person_id === target.person_id)).toBe(false)
  })

  it('give the same list whatever the order of the rows, and break ties by minutes, name and team', async () => {
    const rows = await lf2()
    const target = rows.find(r => r.eligible)!
    expect(similarPlayers([...rows].reverse(), target)).toEqual(similarPlayers(rows, target))
    const a = withPct(target, {}, { person_id: 'feb:a', name: 'A', minutes: 100 })
    const b = withPct(target, {}, { person_id: 'feb:b', name: 'B', minutes: 900 })
    expect(similarPlayers([target, a, b], target).similar.map(s => s.row.person_id)).toEqual(['feb:b', 'feb:a'])
  })

  it('say there is no profile for a row without percentiles, instead of failing', async () => {
    const rows = await lf2()
    const target = { ...rows[0], pct: null, eligible: false }
    expect(similarPlayers(rows, target)).toEqual({ similar: [], reason: 'no-profile' })
  })

  it('does not change the rows it is given', async () => {
    const rows = await lf2()
    const copy = JSON.parse(JSON.stringify(rows))
    similarPlayers(rows, rows[0])
    expect(rows).toEqual(copy)
  })
})
