import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ScopedAccessError } from '@live-package/crypto'
import { DataUnavailable } from '@/datasource/resolve'

const client = vi.hoisted(() => ({ getTeamStats: vi.fn(), API_BASE: '/api/v1' }))
const pbp = vi.hoisted(() => ({ getPointsByOrigin: vi.fn() }))
vi.mock('./client', () => client)
vi.mock('./pbpExtended', () => pbp)

import { getOwnComparison } from './scoutingRival'

// Issue #751: the matchup of the scouting with «Nuestro equipo» chosen is computed on the device from the season rows of the two teams (what `ScoutingRivalService._rows` reads)
// completed with the play-by-play figures of the same competition (an enrichment: the matchup works without them).
const ROWS = [
  { team_id: 1, team_name: 'A', points_per_game: 80, points_against_per_game: 70, possessions_per_game: 70 },
  { team_id: '2', team_name: 'B', points_per_game: 70, points_against_per_game: 75, possessions_per_game: 74 },
  { team_id: 3, team_name: 'C', points_per_game: 90 },
]

beforeEach(() => {
  client.getTeamStats.mockReset().mockResolvedValue({ team_stats: ROWS, opponent_stats: [] })
  pbp.getPointsByOrigin.mockReset().mockResolvedValue([])
})

describe('getOwnComparison', () => {
  it('compares our team with the rival from the season rows (ids as numbers or text) with the best gaps first', async () => {
    const rows = await getOwnComparison('FEB_X', '1', '2')
    expect(client.getTeamStats).toHaveBeenCalledWith('FEB_X')
    const points = rows.find(r => r.key === 'points_per_game')!
    expect(points).toMatchObject({ own: 80, rival: 70, advantage: 'own', own_text: '80,0', rival_text: '70,0' })
    expect(rows.find(r => r.key === 'points_against_per_game')).toMatchObject({ advantage: 'own' })          // fewer conceded is better
    expect(rows.find(r => r.key === 'possessions_per_game')).toMatchObject({ advantage: 'neutral' })         // tempo is style
    expect(rows[rows.length - 1].advantage).toBe('neutral')
  })

  it('the play-by-play figures of the two teams complete their rows', async () => {
    pbp.getPointsByOrigin.mockResolvedValue([
      { team_id: '1', bench_pct: 30, pts_paint_per_game: 36, not_in_the_catalog: 1 },
      { team_id: '2', bench_pct: 20, pts_paint_per_game: null },
      { team_id: '3', bench_pct: 50 },
    ])
    const rows = await getOwnComparison('FEB_X', '1', '2')
    expect(rows.find(r => r.key === 'bench_pct')).toMatchObject({ own: 30, rival: 20, advantage: 'neutral' })
    expect(rows.find(r => r.key === 'pts_paint_per_game')).toBeUndefined()                 // a null figure does not complete the row
    expect(rows.some(r => r.key === 'not_in_the_catalog')).toBe(false)
  })

  it('a team that is not in the season rows leaves nothing to compare', async () => {
    expect(await getOwnComparison('FEB_X', '99', '2')).toEqual([])
    expect(await getOwnComparison('FEB_X', '1', '99')).toEqual([])
  })

  it('when the play-by-play figures are not published the matchup goes on without them', async () => {
    pbp.getPointsByOrigin.mockRejectedValue(new DataUnavailable('no publicado'))
    const rows = await getOwnComparison('FEB_X', '1', '2')
    expect(rows.length).toBeGreaterThan(0)
    expect(rows.some(r => r.key === 'bench_pct')).toBe(false)
  })

  it('a reader without the key is asked for it: that error is not an «enrichment that failed»', async () => {
    pbp.getPointsByOrigin.mockRejectedValue(new ScopedAccessError('sin acceso'))
    await expect(getOwnComparison('FEB_X', '1', '2')).rejects.toBeInstanceOf(ScopedAccessError)
  })
})
