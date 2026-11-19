import { beforeEach, describe, expect, it } from 'vitest'
import { loadCompetitionRows, loadTalentCompetitions, resetTalentData, setTalentBase } from './data'
import { MAX_COMPARED, compareLines, comparePlayers, findPlayers, parseCompare, toggleCompare } from './compare'
import { RADAR_AXES } from './player'
import { toSearchRow, type SearchRow } from './search'
import { serveTalentData, TALENT_BASE } from '@/test/talentDataHost'

/** The comparator of Talent (B5, #881) over the REAL rows of the exporter: LF2 2025 (with bio) and FBCYL 2026 (a player linked to Ana, the rest without bio). Players of different leagues can be compared: each one is read in HIS competition. */
beforeEach(() => { localStorage.clear(); resetTalentData(); setTalentBase(TALENT_BASE); serveTalentData() })

async function all(): Promise<SearchRow[]> {
  const entries = await loadTalentCompetitions()
  const out: SearchRow[] = []
  for (const e of entries) out.push(...(await loadCompetitionRows(e.key)).rows.map(r => toSearchRow(e, r)))
  return out
}

const ANA = 'feb:10100'
const BEA = 'feb:10200'

describe('the list in the address', () => {
  it('reads people separated by commas, without blanks or repeats, and no more than three', () => {
    expect(parseCompare(null)).toEqual([])
    expect(parseCompare('')).toEqual([])
    expect(parseCompare(' feb:1 , feb:2,feb:1,,feb:3,feb:4')).toEqual(['feb:1', 'feb:2', 'feb:3'])
    expect(MAX_COMPARED).toBe(3)
  })

  it('adds a player, takes him out when he is already there and does not go over the limit', () => {
    expect(toggleCompare(['a'], 'b')).toEqual(['a', 'b'])
    expect(toggleCompare(['a', 'b'], 'a')).toEqual(['b'])
    expect(toggleCompare(['a', 'b', 'c'], 'd')).toEqual(['a', 'b', 'c'])
  })
})

describe('the compared players', () => {
  it('are read in their own competition and latest season, in the order they were asked for', async () => {
    const rows = await all()
    const { players, missing } = comparePlayers(rows, [BEA, ANA])
    expect(players.map(p => p.id)).toEqual([BEA, ANA])
    expect(players.map(p => p.row.league)).toEqual(['feb', 'fbcyl'])          // Bea is read in LF2, Ana in her latest season: the FBCYL one linked to her
    expect(missing).toEqual([])
  })

  it('mix leagues: a FBCYL player is read in her FBCYL row, and one linked to a FEB person is that person with her FBCYL season in the trajectory', async () => {
    const rows = await all()
    const alone = rows.find(r => r.league === 'fbcyl' && !r.linked_to)!
    const { players } = comparePlayers(rows, [ANA, alone.person_id])
    expect(players[1].row.league).toBe('fbcyl')
    expect(players[0].seasons).toBe(2)                         // her FEB season and the FBCYL one linked to her
    expect(players[0].row.league).toBe('fbcyl')                // the latest season of the person (2026) is the FBCYL one
  })

  it('say who is missing instead of dropping him without a word', async () => {
    const { players, missing } = comparePlayers(await all(), [ANA, 'feb:no-existe'])
    expect(players.map(p => p.id)).toEqual([ANA])
    expect(missing).toEqual(['feb:no-existe'])
  })

  it('send a linked FBCYL id to the FEB person and never show the same person twice', async () => {
    const rows = await all()
    const linked = rows.find(r => r.linked_to)!
    const { players } = comparePlayers(rows, [linked.person_id, linked.linked_to!])
    expect(players.map(p => p.id)).toEqual([linked.linked_to])
  })
})

describe('the lines of the comparison', () => {
  it('have the bio, the figures per 40 and one percentile per axis of the radar, with a dash where a player has no data and never a zero', async () => {
    const rows = await all()
    const alone = rows.find(r => r.league === 'fbcyl' && !r.linked_to)!
    const lines = compareLines(comparePlayers(rows, [BEA, alone.person_id]).players)
    const pct = lines.filter(l => l.group === 'percentiles')
    expect(pct.map(l => l.key)).toEqual(RADAR_AXES.map(a => a.key))
    const height = lines.find(l => l.key === 'height')!
    expect(height.cells[0].text).toBe('185 cm')
    expect(height.cells[1].text).toBeNull()
  })

  it('mark the best percentile of each axis (all the tied ones), and nothing when only one player has it', async () => {
    const rows = await all()
    const base = comparePlayers(rows, [ANA, BEA]).players
    const withPct = (a: number | null, b: number | null) => compareLines([
      { ...base[0], row: { ...base[0].row, pct: { ...base[0].row.pct!, pts: a } } },
      { ...base[1], row: { ...base[1].row, pct: { ...base[1].row.pct!, pts: b } } },
    ]).find(l => l.key === 'pts' && l.group === 'percentiles')!
    expect(withPct(80, 60).cells.map(c => c.best)).toEqual([true, false])
    expect(withPct(70, 70).cells.map(c => c.best)).toEqual([true, true])
    expect(withPct(70, null).cells.map(c => c.best)).toEqual([false, false])
  })

  it('give the same lines whatever the order of the input rows', async () => {
    const rows = await all()
    expect(compareLines(comparePlayers([...rows].reverse(), [ANA, BEA]).players)).toEqual(compareLines(comparePlayers(rows, [ANA, BEA]).players))
  })
})


describe('finding a player to add', () => {
  it('matches the name without caring about accents, case or order of the words, once per person (a linked FBCYL player is the FEB person), and says nothing for less than two letters', async () => {
    const rows = await all()
    expect(findPlayers(rows, 'a', [])).toEqual([])
    const found = findPlayers(rows, 'prueba ANA', [])
    expect(found.map(f => f.id)).toEqual([ANA])
    expect(found[0].label).toMatch(/2026/)                       // described by his latest season
    expect(findPlayers(rows, 'prueba', []).map(f => f.id)).toEqual(expect.arrayContaining([ANA, BEA]))
    expect(new Set(findPlayers(rows, 'prueba', []).map(f => f.id)).size).toBe(findPlayers(rows, 'prueba', []).length)
  })

  it('leaves out who is already in the comparison and gives no more than the limit, in a fixed order', async () => {
    const rows = await all()
    expect(findPlayers(rows, 'prueba', [ANA]).map(f => f.id)).not.toContain(ANA)
    expect(findPlayers(rows, 'prueba', [], 1)).toHaveLength(1)
    expect(findPlayers([...rows].reverse(), 'prueba', [])).toEqual(findPlayers(rows, 'prueba', []))
  })
})
