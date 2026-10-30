import { describe, expect, it } from 'vitest'
import type { LineupRow } from '@/api/client'
import { lineupAnalysis, type Lineups } from './lineups'
import febVectors from '../../../tests/local_vectors/lineups_feb.json'
import fbcylVectors from '../../../tests/local_vectors/lineups_fbcyl.json'

// Combinaciones on the device (issue #686): every table of the page (size, statistic, period, minimums, last game, game log) equals what `LineupService` answers over the same games,
// from the per-game counters the competition publishes (`tests/local_vectors/lineup_vectors.py`: the real service over the real sample games of both leagues, cut after different periods).
type Json = null | boolean | number | string | Json[] | { [key: string]: Json }

interface Config { name: string; stat?: string; period?: number; last_game?: boolean; include_game_log?: boolean; min_minutes?: number; min_games?: number }

/** Exactly, number for number: the figures are rounded as Python rounds them, so a difference of the last digit is a failure. */
function expectSame(actual: unknown, expected: Json, path = '$'): void {
  if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true)
    expect((actual as unknown[]).length, path).toBe(expected.length)
    expected.forEach((item, i) => expectSame((actual as unknown[])[i], item, `${path}[${i}]`))
  } else if (expected !== null && typeof expected === 'object') {
    expect(actual, path).not.toBeNull()
    expect(Object.keys(actual as object).sort(), path).toEqual(Object.keys(expected).sort())
    for (const [key, value] of Object.entries(expected)) expectSame((actual as Record<string, unknown>)[key], value, `${path}.${key}`)
  } else {
    expect(actual, path).toBe(expected)
  }
}

/** The ties of the sort have no order in the API (the players of a lineup are a `frozenset`): the vectors put each run of equal values in the order of the player ids, and so do we. */
function tiedById(rows: LineupRow[], stat: string): LineupRow[] {
  const out: LineupRow[] = []
  let run: LineupRow[] = []
  const flush = () => { out.push(...run.sort((a, b) => (a.player_ids as string[]).join(',') < (b.player_ids as string[]).join(',') ? -1 : 1)); run = [] }
  for (const row of rows) {
    if (run.length && ((run[0][stat] as number) || 0) !== ((row[stat] as number) || 0)) flush()
    run.push(row)
  }
  flush()
  return out
}

describe.each([['FEB', febVectors], ['FBCYL', fbcylVectors]] as const)('%s: the lineup tables equal what the API answers', (_league, vectors) => {
  const published = vectors.published as unknown as Lineups
  const now = new Date(`${vectors.now}Z`)

  it.each(vectors.cases.map(c => [`${(c.config as Config).name}, size ${c.size}`, c] as const))('%s', (_name, c) => {
    const config = c.config as Config
    const stat = config.stat ?? 'net_rating'
    const rows = lineupAnalysis(published, vectors.team, {
      size: c.size, stat, period: config.period, lastGame: config.last_game, includeGameLog: config.include_game_log, minMinutes: config.min_minutes, minGames: config.min_games, now,
    })
    expect(rows).not.toBeNull()
    expectSame(tiedById(rows as LineupRow[], stat), c.rows as unknown as Json)
  })
})

describe('the lineup tables: the corners', () => {
  const published = febVectors.published as unknown as Lineups
  const now = new Date(`${febVectors.now}Z`)

  it('a team that is not in the publication is left to the API', () => {
    expect(lineupAnalysis(published, 'NOBODY', { size: 5 })).toBeNull()
  })

  it('an unreadable date keeps the game out of every period and the last game, but not out of the season', () => {
    const undated: Lineups = { ...published, teams: [{ ...published.teams[0], games: published.teams[0].games.map((game, i) => (i === 4 ? { ...game, at: null } : game)) }] }
    const last = lineupAnalysis(undated, febVectors.team, { size: 5, lastGame: true, minMinutes: 0, minGames: 0 }) as LineupRow[]
    expect(last.every(row => row.games_played === 1)).toBe(true)
    expect(lineupAnalysis(undated, febVectors.team, { size: 5, period: 7, now, minMinutes: 0, minGames: 0 })).toEqual([])         // the one game of the last week is the undated one
    expect(lineupAnalysis(undated, febVectors.team, { size: 5, minMinutes: 0, minGames: 0 })!.length).toBeGreaterThan(0)
  })

  it('a team with no readable date has no last game', () => {
    const undated: Lineups = { ...published, teams: [{ ...published.teams[0], games: published.teams[0].games.map(game => ({ ...game, at: null })) }] }
    expect(lineupAnalysis(undated, febVectors.team, { size: 5, lastGame: true })).toEqual([])
  })

  it('a player the table does not know is called as the API calls it', () => {
    const nameless: Lineups = { ...published, teams: [{ ...published.teams[0], players: {} }] }
    const row = lineupAnalysis(nameless, febVectors.team, { size: 2, minMinutes: 0, minGames: 0 })![0]
    expect(row.players[0]).toBe(`Player ${(row.player_ids as string[])[0]}`)
    expect(row.player_photo_urls?.[0]).toBeNull()
  })

  it('a size the publication does not have has no lineups', () => {
    expect(lineupAnalysis(published, febVectors.team, { size: 7 })).toEqual([])
  })
})
