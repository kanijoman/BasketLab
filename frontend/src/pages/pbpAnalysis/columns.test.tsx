import { describe, expect, it } from 'vitest'
import type { PeriodRow, SituationRow, TimeoutRow } from '@/api/pbpExtended'
import {
  PERIODS, flattenPeriod, flattenSituations, flattenTimeouts, originColumns, periodColumns, situationColumns, timeoutColumns,
  ORIGIN_REVERSE, PERIOD_REVERSE, SITUATION_REVERSE, TIMEOUT_REVERSE,
} from './columns'

const figures = (pts: number) => ({
  games: 3, minutes: 30, pts, opp_pts: 50, pts_per_game: pts / 3, opp_pts_per_game: 50 / 3, poss: 30, opp_poss: 30, ortg: 100, drtg: 90,
  net_rating: 10, pace: 70, efg_pct: 50, opp_efg_pct: 45, tov_pct: 15, opp_tov_pct: 16, orb_pct: 30, drb_pct: 70, ftr: 25, opp_ftr: 20,
  fouls_per_game: 5, opp_fouls_per_game: 6,
})

const PERIOD_ROWS: PeriodRow[] = [
  { team_id: '1', team_name: 'A', games: 3, games_unreliable: 0, periods: { '1': figures(60), '2': figures(55), OT: figures(10) } },
  { team_id: '2', team_name: 'B', games: 3, games_unreliable: 1, periods: { '1': figures(40), '2': figures(45) } },
]

describe('period rows', () => {
  it('lists Q1-Q4 and OT in order', () => {
    expect(PERIODS.map(p => p.key)).toEqual(['1', '2', '3', '4', 'OT'])
  })

  it('flattens one period per team and drops the teams that never played it', () => {
    expect(flattenPeriod(PERIOD_ROWS, '1').map(r => [r.team_name, r.pts_per_game])).toEqual([['A', 20], ['B', 40 / 3]])
    expect(flattenPeriod(PERIOD_ROWS, 'OT').map(r => r.team_name)).toEqual(['A'])
    expect(flattenPeriod(PERIOD_ROWS, '3')).toEqual([])
  })

  it('keeps the games excluded for an unreliable feed in every row', () => {
    expect(flattenPeriod(PERIOD_ROWS, '1').map(r => r.games_unreliable)).toEqual([0, 1])
  })
})

const SITUATION: SituationRow = {
  team_id: '1', team_name: 'A', games: 3, games_unreliable: 0,
  ato_own: { n: 6, pts: 7, ppp: 7 / 6 }, ato_rival: { n: 2, pts: 1, ppp: 0.5 }, first_poss: { n: 5, pts: 4, ppp: 0.8 },
  edges: {
    start: { pts: 10, opp_pts: 6, poss: 10, opp_poss: 10, tov: 2, opp_tov: 1, pts_per_game: 3.3, net_rating: 40, tov_pct: 20, opp_tov_pct: 10, vs_rest: 15 },
    end: { pts: 4, opp_pts: 8, poss: 10, opp_poss: 10, tov: 3, opp_tov: 2, pts_per_game: 1.3, net_rating: -40, tov_pct: 30, opp_tov_pct: 20, vs_rest: -65 },
    rest: { pts: 26, opp_pts: 16, poss: 20, opp_poss: 20, tov: 3, opp_tov: 4, pts_per_game: 8.7, net_rating: 25, tov_pct: 15, opp_tov_pct: 20 },
  },
}

describe('situation rows', () => {
  it('flattens the after-timeout, first-possession and edge figures', () => {
    const [row] = flattenSituations([SITUATION])

    expect(row).toMatchObject({
      team_name: 'A', ato_own_n: 6, ato_own_ppp: 7 / 6, ato_rival_n: 2, first_poss_ppp: 0.8,
      start_net: 40, start_vs_rest: 15, start_tov_pct: 20, end_net: -40, end_vs_rest: -65, end_tov_pct: 30,
    })
  })
})

const TIMEOUT: TimeoutRow = {
  team_id: '1', team_name: 'A',
  own: { n: 4, net_rating_before: -10, net_rating_after: 20, delta_net_rating: 30, pct_caller_improves: 75 },
  rival: { n: 0, net_rating_before: null, net_rating_after: null, delta_net_rating: null, pct_caller_improves: null },
}

describe('timeout rows', () => {
  it('flattens both groups and keeps the empty one as missing values', () => {
    const [row] = flattenTimeouts([TIMEOUT])

    expect(row).toMatchObject({ own_n: 4, own_delta: 30, own_pct: 75, rival_n: 0, rival_delta: null, rival_pct: null })
  })
})

describe('columns', () => {
  const ids = (cols: { id?: string; accessorKey?: unknown; columns?: unknown[] }[]): string[] =>
    cols.flatMap(c => (c.columns ? ids(c.columns as never) : [String(c.id ?? c.accessorKey)]))

  it('own and conceded views of the origins have the same shape and a team column first', () => {
    const own = ids(originColumns('own') as never), opp = ids(originColumns('opp') as never)

    expect(own[0]).toBe('team_name')
    expect(own.map(i => i.replace('opp_', ''))).toEqual(opp.map(i => i.replace('opp_', '')))
    expect(opp).toContain('opp_pts_off_tov_per_game')
  })

  it('every reverse (lower is better) column exists in its table', () => {
    expect(ids(periodColumns() as never)).toEqual(expect.arrayContaining(PERIOD_REVERSE))
    expect(ids(situationColumns() as never)).toEqual(expect.arrayContaining(SITUATION_REVERSE))
    expect(ids(timeoutColumns() as never)).toEqual(expect.arrayContaining(TIMEOUT_REVERSE))
    expect(ids(originColumns('opp') as never)).toEqual(expect.arrayContaining(ORIGIN_REVERSE.opp))
    expect(ORIGIN_REVERSE.own).toEqual([])
  })

  it('the conceded points are all reverse columns: fewer is better', () => {
    expect(ORIGIN_REVERSE.opp.every(c => c.startsWith('opp_'))).toBe(true)
    expect(PERIOD_REVERSE).toEqual(expect.arrayContaining(['drtg', 'opp_pts_per_game', 'tov_pct']))
  })
})
