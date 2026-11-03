import { describe, expect, it } from 'vitest'
import vectors from '../../../tests/local_vectors/weekly_rows.json'
import {
  ADV_HEADERS, BASIC_HEADERS, CONSISTENCY_HEADERS, LAST_MATCH_HEADERS, advancedRows, basicRows, calcQuartiles, comparativeAdvancedRows, comparativeBasicRows, consistencyRows,
  lastMatchRows, playerRows, quartileTone, sf, withDiff, type Row, type Tone,
} from './weeklyRows'

// The rows of the weekly report in the browser (issue #716, D4a) say what the server's `_weekly_report_helpers` say: the same text in every cell and the same rating. The vectors are
// what Python answers for the sample league and a league of awkward floats (`tests/local_vectors/weekly_report_vectors.py`); the colours of matplotlib are the tones here.
const TONE_OF_HEX: Record<string, Tone> = { '#0d1117': 'plain', '#14532d': 'q1', '#5a3e00': 'q2', '#3d2000': 'q3', '#500000': 'q4', '#1e2530': 'even' }
const tones = (colors: string[][]) => colors.map(row => row.map(hex => TONE_OF_HEX[hex]))

type Expected = { texts: string[][]; colors: string[][] }
const same = (got: { texts: string[][]; tones: Tone[][] }, want: Expected) => {
  expect(got.texts).toEqual(want.texts)
  expect(got.tones).toEqual(tones(want.colors))
}

describe.each(vectors.leagues)('the rows of the $name league are those of the server', league => {
  const teams = league.teams as Row[]

  it.each(['False', 'True'])('basic and advanced tables of the competition (rival table: %s)', inverted => {
    const invert = inverted === 'True'
    same(basicRows(teams, invert), league.basic[inverted as 'False'])
    same(advancedRows(teams, invert), league.advanced[inverted as 'False'])
  })

  it.each(['False', 'True'])('comparative tables with the real difference (rival table: %s)', inverted => {
    const invert = inverted === 'True'
    same(comparativeBasicRows(league.comparative as never, invert), league.comparative_basic[inverted as 'False'])
    same(comparativeAdvancedRows(league.comparative as never, invert), league.comparative_advanced[inverted as 'False'])
  })

  it.each(['avg', 'total', 'projection'] as const)('players table, %s', mode => {
    const got = playerRows(league.players as Row[], mode)
    expect(got.headers).toEqual(league.player_rows[mode].headers)
    same(got, league.player_rows[mode])
  })

  it('consistency of the teams', () => same(consistencyRows(league.consistency as never), league.consistency_rows))

  it('last match', () => {
    if (!('last_match' in league)) return
    same(lastMatchRows(teams[0], teams[1], teams[2], teams[3], String(teams[0].team_name), String(teams[1].team_name)), league.last_match as Expected)
  })
})

describe('the headers are the server\'s', () => {
  it('are the same columns in the same order', () => {
    expect([BASIC_HEADERS, ADV_HEADERS, LAST_MATCH_HEADERS, CONSISTENCY_HEADERS]).toEqual([vectors.headers.basic, vectors.headers.advanced, vectors.headers.last_match, vectors.headers.consistency])
  })
})

describe('the small pieces', () => {
  it('a missing figure is a dash and the rest have their decimals', () => {
    expect([sf(null), sf(undefined), sf(12.25), sf(0.05, 1), sf(2.675, 2)]).toEqual(['-', '-', '12.2', '0.1', '2.67'])   // Python rounds the exact ties to the even digit
  })

  it('a difference that rounds to nothing is 0.0 with no sign, and one without a rival to compare with is only the figure', () => {
    expect([withDiff(10.04, 10), withDiff(9.96, 10), withDiff(10, null), withDiff(12.5, 10), withDiff(8, 10.2)]).toEqual(['10.0 (0.0)', '10.0 (0.0)', '10.0', '12.5 (+2.5)', '8.0 (-2.2)'])
  })

  it('has no quartiles to rate without figures and rates with the thresholds of numpy', () => {
    expect(calcQuartiles([])).toEqual([0, 0, 0])
    expect(calcQuartiles([null, 4, 1, 3, 2])).toEqual([1.75, 2.5, 3.25])
    expect([5, 3, 2, 1].map(v => quartileTone(v, [1.75, 2.5, 3.25]))).toEqual(['q1', 'q2', 'q3', 'q4'])
    expect([5, 1].map(v => quartileTone(v, [1.75, 2.5, 3.25], true))).toEqual(['q4', 'q1'])      // less is better: the colours turn round
  })
})
