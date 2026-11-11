import { describe, expect, it } from 'vitest'
import { buildGames, type GameResult } from '../gameLog'
import { walkForwardHeadline, walkForwardPreviews, walkForwardSeason } from './walkForward'
import { primera } from '@/test/forecastFixtures'

// The walk-forward evaluation (#851) on a REAL season (Primera FEB 2025-26: 271 games, 17 teams; the first 150 here so it is quick): every forecast is made with the games BEFORE the one it is judged
// on and nothing else. The most important test is that there is no leak: changing what happened afterwards cannot change what was forecast.
const all = buildGames(primera().team_rows)
const games = all.slice(0, 150)
/** The same games with every result after `index` turned round: whatever is forecast about the games up to `index` must not notice. */
const flippedAfter = (index: number): GameResult[] => games.map((g, i) => (i > index ? { ...g, margin: -g.margin, homePoints: g.awayPoints, awayPoints: g.homePoints } : g))

describe('the headline, game by game', () => {
  const rows = walkForwardHeadline(games, 'M')

  it('has a forecast for every game, in order, of what that game turned out to be', () => {
    expect(rows).toHaveLength(150)
    expect(rows.map(r => r.k)).toEqual(games.map((_, i) => i))
    expect(rows.every(r => r.p > 0 && r.p < 1 && (r.y === 0 || r.y === 1))).toBe(true)
    expect(rows.map(r => r.y)).toEqual(games.map(g => (g.margin > 0 ? 1 : 0)))
  })

  it('knows nothing of the teams at the first game: only the home court of the family favours the home team', () => {
    expect(rows[0].p).toBeGreaterThan(0.5)
    expect(rows[0].played).toBe(0)
  })

  it('does not leak: turning round every result after a game does not change what was forecast up to it', () => {
    const other = walkForwardHeadline(flippedAfter(100), 'M')
    expect(other.slice(0, 101)).toEqual(rows.slice(0, 101))
    expect(other[130].p).not.toBe(rows[130].p)
  })

  it('says how many games the least known of the two teams had played, and that grows', () => {
    expect(rows[140].played).toBeGreaterThan(rows[10].played)
    expect(rows.every(r => r.played >= 0)).toBe(true)
  })

  it('beats a coin toss once the teams are known (the log loss of the games with ten or more previous ones is under ln 2)', () => {
    const known = rows.filter(r => r.played >= 10)
    expect(known.length).toBeGreaterThan(10)
    expect(known.reduce((s, r) => s - (r.y * Math.log(r.p) + (1 - r.y) * Math.log(1 - r.p)), 0) / known.length).toBeLessThan(Math.LN2)
  })

  it('has the baseline of the home team winning as often as it has so far', () => {
    expect(rows[0].baseline).toBe(0.5)
    expect(rows.every(r => r.baseline > 0 && r.baseline < 1)).toBe(true)
  })
})

describe('the previews, game by game', () => {
  const study = walkForwardPreviews(games, 'M', { from: 60, every: 30 })

  it('are made at the games asked for with only the games before them', () => {
    expect(study.samples.map(s => s.k)).toEqual([60, 90, 120])
    expect(study.skipped).toBe(0)
  })

  it('give back the headline probability exactly: the pool is anchored every time', () => {
    expect(study.anchoredFailures).toBe(0)
    expect(study.samples.every(s => s.muShift !== undefined && Math.abs(s.muShift) < 15)).toBe(true)
  })

  it('say how spread the scenarios were and what is left for the kernel', () => {
    for (const s of study.samples) {
      expect(s.residualSd).toBeGreaterThan(5)
      expect(s.sigmaU).toBeGreaterThanOrEqual(3)
    }
  })

  it('score the four kinds of game against what happened, with a baseline of how often each happened before', () => {
    expect(study.buckets.n).toBe(3)
    expect(study.buckets.brier).toBeGreaterThan(0)
    expect(study.buckets.brierBaseline).toBeGreaterThan(0)
  })

  it('check every objective from the side of both teams: was it reached in the game, and who won', () => {
    expect(study.levers.length).toBeGreaterThan(10)
    for (const l of study.levers) {
      expect(l.pWin).toBeGreaterThan(0)
      expect(l.pWin).toBeLessThan(1)
      expect([0, 0.5, 1]).toContain(l.y)
      expect(typeof l.met).toBe('boolean')
    }
    expect(study.levers.some(l => l.met)).toBe(true)
    expect(study.levers.some(l => !l.met)).toBe(true)
  })

  it('does not leak: turning round what happens after a sample does not change that sample', () => {
    const other = walkForwardPreviews(flippedAfter(90), 'M', { from: 60, every: 30 })
    expect(other.samples.slice(0, 2)).toEqual(study.samples.slice(0, 2))
  })
})

describe('the simulation of the league, cut after cut', () => {
  const rows = walkForwardSeason(games, 'M', { cuts: [0.25, 0.5, 0.75], simulations: 500 })

  it('has one row per cut, with the games played before it and the teams', () => {
    expect(rows.map(r => r.cut)).toEqual([0.25, 0.5, 0.75])
    expect(rows.map(r => r.played)).toEqual([37, 75, 112])
    expect(rows.every(r => r.teams === 17 && r.ms >= 0)).toBe(true)
  })

  it('scores the distribution of the final position and the baseline of keeping the order of today', () => {
    for (const r of rows) {
      expect(r.rps).toBeGreaterThan(0)
      expect(r.rps).toBeLessThan(1)
      expect(r.rpsBaseline).toBeGreaterThan(0)
      expect(r.brierFirst).toBeGreaterThanOrEqual(0)
      expect(r.brierTop4).toBeGreaterThanOrEqual(0)
    }
  })

  it('does better than keeping today\'s order on average over the cuts', () => {
    const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length
    expect(mean(rows.map(r => r.rps))).toBeLessThan(mean(rows.map(r => r.rpsBaseline)))
  })
})
