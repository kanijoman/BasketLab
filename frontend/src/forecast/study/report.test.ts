import { describe, expect, it } from 'vitest'
import { buildGames } from '../gameLog'
import { formatReport, type CompetitionResult } from './report'
import { walkForwardHeadline, walkForwardPreviews, walkForwardSeason } from './walkForward'
import { primera } from '@/test/forecastFixtures'

// The report of the walk-forward evaluation (#851), written from the results of a REAL season (the first 130 games of the Primera FEB 2025-26): every section is there, in Spanish, with numbers.
const games = buildGames(primera().team_rows).slice(0, 130)
const result: CompetitionResult = {
  name: 'PRIMERA_FEB_2025_2026_Liga_Regular_Único', gender: 'M', games: games.length,
  headline: walkForwardHeadline(games, 'M'), previews: walkForwardPreviews(games, 'M', { from: 50, every: 20 }), season: walkForwardSeason(games, 'M', { simulations: 300 }),
}
const report = formatReport([result], '2026-11-11')

describe('the report', () => {
  it('has the sections of the evaluation in order', () => {
    const headings = [...report.matchAll(/^#{1,3} (.+)$/gm)].map(m => m[1])
    expect(headings).toEqual(expect.arrayContaining(['Pronóstico del partido', 'Escenarios', 'Objetivos del partido', 'Simulación de la liga', 'Límites']))
    expect(report.indexOf('Pronóstico del partido')).toBeLessThan(report.indexOf('Escenarios'))
    expect(report.indexOf('Escenarios')).toBeLessThan(report.indexOf('Objetivos del partido'))
  })

  it('has a row per bucket of previous games, per cut and per bin of calibration, in markdown tables', () => {
    for (const bucket of ['0-2', '3-5', '6-9', '10+']) expect(report).toContain(`| ${bucket} |`)
    for (const cut of ['25 %', '50 %', '75 %']) expect(report).toContain(`| ${cut} |`)
    expect(report.match(/^\| --- /gm)!.length).toBeGreaterThanOrEqual(5)
  })

  it('says what was evaluated and on what, and the date', () => {
    expect(report).toContain('PRIMERA_FEB_2025_2026_Liga_Regular_Único')
    expect(report).toContain('2026-11-11')
    expect(report).toContain('130 partidos')
  })

  it('has no NaN, undefined or infinity in it', () => {
    expect(report).not.toMatch(/NaN|undefined|Infinity/)
  })

  it('uses the decimal comma', () => {
    expect(report).toMatch(/\d,\d{3}/)
    expect(report).not.toMatch(/\| \d\.\d{3} \|/)
  })
})
