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
      games: { own: 20, rival: 18, league: 120 },
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
})
