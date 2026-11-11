import { describe, expect, it } from 'vitest'
import { buildGames } from './gameLog'
import { buildModel } from './pool'
import { buildPreview, MIN_GAMES, MIN_POOL } from './preview'
import { fbcyl, lfChallenge, lfChallengeCalendar, primera } from '@/test/forecastFixtures'

// The preview of a match, composed on real competitions: the headline (always), and, when there are enough games to compare with, the scenarios, the objectives and the matchup.
describe('the preview of a match in a complete season', () => {
  const f = primera()
  const games = buildGames(f.team_rows)
  const model = buildModel(games, f.gender)
  const [own, rival] = [games[0].home, games[0].away]

  it('has the headline, the scenarios, the objectives and the matchup, and a normal confidence', () => {
    const p = buildPreview(model, own, rival, 'own')
    expect(p.confidence).toEqual({ level: 'normal', reasons: [] })
    expect(p.headline.p).toBeGreaterThan(0)
    expect(p.detail!.scenarios).toHaveLength(4)
    expect(p.detail!.matchup).toHaveLength(4)
    expect(p.detail!.poolSize).toBe(542)
    expect(p.detail!.anchored).toBe(true)
    expect(p.detail!.levers.attack.length + p.detail!.levers.defence.length).toBeGreaterThan(0)
  })

  it('remembers who is who and where it is played', () => {
    const p = buildPreview(model, own, rival, 'rival')
    expect([p.own, p.rival, p.court]).toEqual([own, rival, 'rival'])
  })
})

describe('the preview early in a season (LF Challenge, 9/11/2026)', () => {
  const f = lfChallenge()
  const archive = buildGames(f.team_rows)                                  // the 39 games the archive has
  const withCalendar = buildGames(f.team_rows, lfChallengeCalendar())      // plus the 8 results only the calendar has
  const model = buildModel(archive, f.gender)
  const played = (games: typeof archive, team: string) => games.filter(g => g.home === team || g.away === team).length
  const teams = [...new Set(archive.flatMap(g => [g.home, g.away]))]
  const young = teams.find(t => played(archive, t) < MIN_GAMES)!
  const old = teams.find(t => played(archive, t) >= MIN_GAMES)!

  it('is of low confidence when a team has played less than five games, and says which one and how many', () => {
    const p = buildPreview(model, young, old, 'own')
    expect(p.confidence.level).toBe('baja')
    expect(p.confidence.reasons).toEqual([{ kind: 'few-games', team: young, name: expect.any(String), games: played(archive, young) }])
    expect(p.detail).not.toBeNull()
  })

  it('is of normal confidence when both teams have played enough', () => {
    const other = teams.find(t => played(archive, t) >= MIN_GAMES && t !== old)!
    expect(buildPreview(model, old, other, 'neutral').confidence.level).toBe('normal')
  })

  it('counts the results of the calendar among the games of a team: they can lift it over the minimum', () => {
    expect(withCalendar.length).toBe(47)
    const lifted = teams.filter(t => played(archive, t) < MIN_GAMES && played(withCalendar, t) >= MIN_GAMES)
    expect(lifted.length).toBeGreaterThan(0)
    const full = buildModel(withCalendar, f.gender)
    expect(buildPreview(full, lifted[0], old, 'own').confidence.reasons.filter(r => r.kind === 'few-games' && r.team === lifted[0])).toEqual([])
  })
})

describe('the awkward previews', () => {
  it('with too few scenarios to compare with only the headline is shown (a handful of games at the start of a season)', () => {
    const f = fbcyl()
    const firstGames = buildGames(f.team_rows).slice(0, 5)
    const rows = f.team_rows.filter(r => firstGames.some(g => g.id === String(r.match_id)))
    const model = buildModel(buildGames(rows), f.gender)
    expect(model.pool.length).toBeLessThan(MIN_POOL)
    const p = buildPreview(model, firstGames[0].home, firstGames[0].away, 'own')
    expect(p.detail).toBeNull()
    expect(p.headline.p).toBeGreaterThan(0)
    expect(p.confidence.level).toBe('baja')
    expect(p.confidence.reasons).toContainEqual({ kind: 'small-pool', size: model.pool.length })
  })

  it('a team with no games has the league average, a coin toss at a neutral court, and says it has played nothing', () => {
    const model = buildModel(buildGames(primera().team_rows), 'M')
    const p = buildPreview(model, 'nobody', 'nobody-else', 'neutral')
    expect(p.headline.p).toBe(0.5)
    expect(p.confidence.reasons.filter(r => r.kind === 'few-games').map(r => r.kind === 'few-games' && r.games)).toEqual([0, 0])
  })

  it('a competition without any game is a headline of a coin toss and nothing else', () => {
    const p = buildPreview(buildModel([], 'F'), 'A', 'B', 'own')
    expect(p.detail).toBeNull()
    expect(p.confidence.level).toBe('baja')
    expect(p.headline.p).toBeGreaterThan(0.5)                                      // the home court of the family, nothing else
  })

  it('FBCYL has its previews too, with the calibrated spread of its family', () => {
    const f = fbcyl()
    const games = buildGames(f.team_rows)
    const p = buildPreview(buildModel(games, f.gender), games[0].home, games[0].away, 'own')
    expect(p.headline.sigma).toBe(14)
  })
})
