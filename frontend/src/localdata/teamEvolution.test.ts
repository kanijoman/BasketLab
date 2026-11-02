import { describe, expect, it } from 'vitest'
import { teamEvolution } from './evolution'
import type { GameRow } from './aggregateTeams'
import febTeams from '../../../tests/local_vectors/team_stats_feb.json'
import fbcylTeams from '../../../tests/local_vectors/team_stats_fbcyl.json'
import febEvolution from '../../../tests/local_vectors/team_evolution_feb.json'
import fbcylEvolution from '../../../tests/local_vectors/team_evolution_fbcyl.json'

// The evolution of ONE team on the device (issue #708): game by game with its date, opponent, rolling and cumulative averages, exactly what `EvolutionService.get_team_evolution`
// answers (`tests/local_vectors/generate.py`: the real per-game pipelines of each league, every stat of every team, and the extreme windows).
describe.each([['FEB', febTeams.rows, febEvolution.cases], ['FBCYL', fbcylTeams.rows, fbcylEvolution.cases]] as const)('%s: the evolution of a team equals the API', (_league, rows, cases) => {
  it.each(cases.map(c => [`team ${c.team_id}, ${c.stat} (window ${c.window})`, c] as const))('%s', (_name, c) => {
    expect(teamEvolution(rows as unknown as GameRow[], c.team_id, c.stat, c.window)).toEqual(c.points)
  })
})

describe('teamEvolution: the corners', () => {
  const rows = febTeams.rows as unknown as GameRow[]

  it('a team that is not in the rows has no games', () => {
    expect(teamEvolution(rows, 'NOBODY', 'points', 5)).toEqual([])
    expect(teamEvolution([], '101', 'points', 5)).toEqual([])
  })

  it('a stat the API does not know is read as points, as the router does', () => {
    expect(teamEvolution(rows, rows[0].team_id, 'nonsense', 5)).toEqual(teamEvolution(rows, rows[0].team_id, 'points', 5))
  })

  it('a ratio with no denominator has no value in that game and the averages skip it', () => {
    const own = rows.filter(r => r.team_id === rows[0].team_id)
    const spoiled = rows.map(r => (r === own[1] ? { ...r, fg2_attempts: 0, fg2_made: 0 } : r))
    const points = teamEvolution(spoiled, rows[0].team_id, 'fg2_percentage', 3)
    expect(points[1].value).toBeNull()
    expect(points[1].rolling_avg).toBe(points[0].value)               // only the first game counts in the window
    expect(points[1].cumulative_avg).toBe(points[0].value)
    expect(points[2].value).not.toBeNull()
  })

  it('a game with no readable date goes last and is dated "unknown"', () => {
    const id = rows[0].team_id
    const own = rows.filter(r => r.team_id === id)
    const spoiled = rows.map(r => (r === own[0] ? { ...r, starttime: null } : r))
    const points = teamEvolution(spoiled, id, 'points', 5)
    expect(points[points.length - 1].game_date).toBe('unknown')
    expect(points.slice(0, -1).every(p => /^\d{4}-\d{2}-\d{2}$/.test(p.game_date))).toBe(true)
  })
})
