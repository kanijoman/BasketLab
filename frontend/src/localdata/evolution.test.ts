import { describe, expect, it } from 'vitest'
import { competitionEvolution, EVOLUTION_STATS } from './evolution'
import type { GameRow } from './aggregateTeams'
import febTeams from '../../../tests/local_vectors/team_stats_feb.json'
import fbcylTeams from '../../../tests/local_vectors/team_stats_fbcyl.json'
import febEvolution from '../../../tests/local_vectors/evolution_feb.json'
import fbcylEvolution from '../../../tests/local_vectors/evolution_fbcyl.json'

// Evolución on the device (issue #672): the competition-wide rolling and cumulative averages from the rows of the contract equal what `EvolutionService` answers
// (`tests/local_vectors/generate.py`: its real per-game pipelines of each league, every stat, two windows).
describe.each([['FEB', febTeams.rows, febEvolution.cases], ['FBCYL', fbcylTeams.rows, fbcylEvolution.cases]] as const)('%s: the evolution equals the API', (_league, rows, cases) => {
  it('the vectors cover every stat the page can ask for', () => {
    expect([...new Set(cases.map(c => c.stat))].sort()).toEqual([...EVOLUTION_STATS].sort())
  })

  it.each(cases.map(c => [`${c.stat} (window ${c.window})`, c] as const))('%s', (_name, c) => {
    const got = competitionEvolution(rows as unknown as GameRow[], c.stat, c.window)
    expect(got.map(p => p.game_number)).toEqual(c.points.map(p => p.game_number))
    c.points.forEach((want, i) => {
      for (const key of ['competition_rolling', 'competition_cumulative'] as const) {
        if (want[key] === null) expect(got[i][key], `${key} at ${i + 1}`).toBeNull()
        else expect(got[i][key] as number, `${key} at ${i + 1}`).toBeCloseTo(want[key] as number, 2)
      }
    })
  })
})

describe('competitionEvolution: the corners', () => {
  const rows = febTeams.rows as unknown as GameRow[]

  it('no rows is no points', () => {
    expect(competitionEvolution([], 'points')).toEqual([])
  })

  it('a stat nobody has (a key the API does not know) has no value at any game', () => {
    expect(competitionEvolution(rows, 'nonsense').every(p => p.competition_rolling === null && p.competition_cumulative === null)).toBe(true)
  })

  it('a game with no readable date goes last for its team, as the pipeline sorts its "unknown" date', () => {
    const team = rows.filter(r => r.team_id === rows[0].team_id)
    const shuffled = team.map((r, i) => (i === 0 ? { ...r, starttime: 'sin fecha', points: 1000 } : r))
    const points = competitionEvolution(shuffled, 'points', 2)
    expect(points).toHaveLength(team.length)
    expect(points[team.length - 1].competition_cumulative).toBeGreaterThan(points[0].competition_cumulative as number)    // the 1000 comes last, not first
  })

  it('games played the same day keep the order of the rows', () => {
    const [a, b] = rows.filter(r => r.team_id === rows[0].team_id).slice(0, 2)
    const day = { ...a, starttime: '03-10-2025 - 12:30' }
    const one = competitionEvolution([day, { ...b, starttime: '03-10-2025 - 20:30', points: 7 }], 'points', 2)
    const two = competitionEvolution([{ ...b, starttime: '03-10-2025 - 20:30', points: 7 }, day], 'points', 2)
    expect(one[0].competition_cumulative).toBe(day.points)
    expect(two[0].competition_cumulative).toBe(7)
  })
})
