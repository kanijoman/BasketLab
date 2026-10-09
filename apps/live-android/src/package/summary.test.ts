import { describe, expect, it } from 'vitest'
import { summarizePackage } from './summary'

const pkg = (over: Record<string, unknown> = {}) =>
  JSON.stringify({
    checksum: 'x',
    package: {
      team: { id: '1', name: 'EQUIPO PROPIO' }, rival: { id: '2', name: 'EQUIPO RIVAL' },
      season: '2025-2026', collection: 'FEB_X', created_at: '2026-10-08T12:00:00Z',
      tables: { players: { a: {}, b: {}, c: {} }, rival_players: { x: {}, y: {} } },
      baselines: { sample_games: { own: 20, rival: 18, league: 120 } },
      ...over,
    },
  })

describe('summarizePackage', () => {
  it('describes the package for the user', () => {
    expect(summarizePackage(pkg())).toEqual({
      team: 'EQUIPO PROPIO', rival: 'EQUIPO RIVAL', season: '2025-2026', collection: 'FEB_X',
      createdAt: '2026-10-08T12:00:00Z', ownPlayers: 3, rivalPlayers: 2,
      games: { own: 20, rival: 18, league: 120 }, match: null,
    })
  })

  it('tolerates missing optional sections', () => {
    const s = summarizePackage(pkg({ tables: {}, baselines: {} }))
    expect(s.ownPlayers).toBe(0)
    expect(s.games).toEqual({ own: 0, rival: 0, league: 0 })
  })

  it('throws on text that is not a package', () => {
    expect(() => summarizePackage('nope')).toThrow()
  })

  it('includes the match the package was prepared for', () => {
    const match = { code: '2524465', start: '2026-10-10T19:00', home: { id: '1', name: 'EQUIPO PROPIO' }, away: { id: '2', name: 'EQUIPO RIVAL' } }
    expect(summarizePackage(pkg({ competition_meta: { match } })).match).toEqual(match)
  })

  it('keeps only the code when the calendar details were not available', () => {
    expect(summarizePackage(pkg({ competition_meta: { match: { code: '77' } } })).match).toEqual({ code: '77' })
  })
})
