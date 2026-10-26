import { describe, expect, it } from 'vitest'
import type { BoxscoreEntry, LastStat, Snapshot, SnapshotPlayer } from '../../engine/types'
import { ADVANCED_COLUMNS, NORMAL_COLUMNS, cellText, highlightFor, playerRows, teamRows } from './model'

const stats = (over: Partial<SnapshotPlayer['stats']> = {}) => ({ fg2m: 0, fg2a: 0, fg3m: 0, fg3a: 0, ftm: 0, fta: 0, orb: 0, drb: 0, tov: 0, stl: 0, ast: 0, blk: 0, ...over })
const player = (name: string, team: string, over: Partial<SnapshotPlayer> = {}): SnapshotPlayer =>
  ({ name, team_id: team, on_court: false, minutes: 0, pf: 0, pts: 0, pm: 0, fd: 0, stats: stats(), ...over })

const SNAP = {
  period: 2, remaining: 300, elapsed: 900, score: { A: 10, B: 8 }, home_id: 'A',
  teams: {
    A: { name: 'LOCAL', fouls_game: 3, stats: { ...stats({ fg2m: 4, fg2a: 8, orb: 3, drb: 7, tov: 5, ftm: 2, fta: 3 }), tov_team: 1, pts: 10 } },
    B: { name: 'VISIT', fouls_game: 2, stats: { ...stats(), tov_team: 0, pts: 8 } },
  },
  players: {
    p3: player('C. TERCERA', 'A', { minutes: 300, stats: stats({ fg2m: 1, fg2a: 2, orb: 1 }) }),
    p1: player('A. PRIMERA', 'A', { on_court: true, minutes: 872, pts: 7, fd: 2, pf: 1, pm: 4, stats: stats({ fg2m: 2, fg2a: 3, fg3m: 1, fg3a: 2, ftm: 2, fta: 3, drb: 4, ast: 2, stl: 1, tov: 2 }) }),
    p2: player('B. SEGUNDA', 'A', { on_court: true, minutes: 60 }),
    r1: player('R. RIVAL', 'B', { on_court: true, minutes: 900 }),
  },
  last_stat: null,
} as unknown as Snapshot

const ENTRIES: Record<string, BoxscoreEntry> = {
  p1: { val: 11, adv: { usage: 21.04, orating: 110.2, drating: 98.7, net_rtg: 11.5, efg: 62.5, ts: 60.1, ftr: 37.5, three_pr: 40, ast_pct: 18, tov_pct: 12.3, stl_pct: 2.1, blk_pct: null, drb_pct: 11, orb_pct: 0, pie: 14.256 }, dev: { pts: 0.8, tov: -0.4 } },
}

describe('the rows of a team', () => {
  it('has the players of the team only, the ones on court first and each group in a steady order', () => {
    expect(playerRows(SNAP, 'A', ENTRIES).map(r => r.id)).toEqual(['p1', 'p2', 'p3'])
  })

  it('a player who is not in the snapshot yet is not invented', () => {
    expect(playerRows({ ...SNAP, players: undefined }, 'A', ENTRIES)).toEqual([])
  })

  it('adds the row of the team: its rebounds and turnovers minus the players\' are the ones nobody owns', () => {
    const { team, totals } = teamRows(SNAP, 'A', playerRows(SNAP, 'A', ENTRIES))
    expect(team.stats).toMatchObject({ orb: 3 - 1, drb: 7 - 4, tov: 5 + 1 - 2 })     // team turnovers are the 1 of tov_team plus what no player owns
    expect(totals.pts).toBe(10)
  })
})

describe('the cells', () => {
  const row = playerRows(SNAP, 'A', ENTRIES)[0]
  const by = (id: string) => [...NORMAL_COLUMNS, ...ADVANCED_COLUMNS].find(c => c.id === id)!

  it('say the minutes as the PDF does and the shooting as made/attempted', () => {
    expect(cellText(by('min'), row)).toBe('14:32')
    expect(cellText(by('t2'), row)).toBe('2/3')
    expect(cellText(by('t3'), row)).toBe('1/2')
    expect(cellText(by('tc'), row)).toBe('3/5')
    expect(cellText(by('tl'), row)).toBe('2/3')
  })

  it('say the rebounds, the fouls committed and drawn, the plus/minus with sign and the valuation', () => {
    expect([by('ro'), by('rd'), by('rt'), by('fc'), by('fr'), by('pm'), by('val')].map(c => cellText(c, row))).toEqual(['0', '4', '4', '1', '2', '+4', '11'])
  })

  it('say the advanced figures with a decimal comma and a dash when there is nothing to say', () => {
    expect(cellText(by('usage'), row)).toBe('21,0')
    expect(cellText(by('pie'), row)).toBe('14,3')
    expect(cellText(by('blk_pct'), row)).toBe('—')
  })

  it('a player without advanced figures yet has dashes', () => {
    expect(cellText(by('usage'), playerRows(SNAP, 'A', ENTRIES)[1])).toBe('—')
  })
})

describe('what the last action lights', () => {
  const rows = playerRows(SNAP, 'A', ENTRIES)
  const last = (over: Partial<LastStat>): LastStat => ({ seq: 5, player_id: 'p1', team_id: 'A', keys: ['pts', 'fg2m', 'fg2a'], also: [], ...over })

  it('lights the row of the player and the cells of the columns that changed', () => {
    const light = highlightFor(last({}), 'p1')
    expect(light?.row).toBe(true)
    expect(NORMAL_COLUMNS.filter(c => light?.cell(c)).map(c => c.id)).toEqual(['pts', 't2', 'tc'])
  })

  it('the player who draws a foul lights his drawn-fouls cell', () => {
    const l = last({ player_id: 'p2', keys: ['pf'], also: [{ player_id: 'p1', team_id: 'A', keys: ['fd'] }] })
    expect(NORMAL_COLUMNS.filter(c => highlightFor(l, 'p1')?.cell(c)).map(c => c.id)).toEqual(['fr'])
    expect(NORMAL_COLUMNS.filter(c => highlightFor(l, 'p2')?.cell(c)).map(c => c.id)).toEqual(['fc'])
  })

  it('nobody else, and nothing before the first action', () => {
    expect(highlightFor(last({}), 'p3')).toBeNull()
    expect(highlightFor(null, 'p1')).toBeNull()
    expect(rows).toHaveLength(3)
  })

  it('a substitution lights the row but no cell', () => {
    const light = highlightFor(last({ keys: ['on_court'] }), 'p1')
    expect(light?.row).toBe(true)
    expect(NORMAL_COLUMNS.some(c => light?.cell(c))).toBe(false)
  })
})
