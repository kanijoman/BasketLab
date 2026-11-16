// The walk-forward evaluation of the projection of a match (#938) over the real competitions of an export. Not a test of the CI: run it by hand,
//   python scripts/web_data_dump.py --out DIR                (the published rows of web-data; or python run_local_export.py)
//   cd frontend && FORECAST_STUDY_DIR=DIR npm run study:projection
// and it writes the report to `test-results/projection-study.md` (git-ignored); the figures that matter go to docs/evaluaciones/. Settings (environment): those of `competitions.ts`,
// `FORECAST_STUDY_OUT` (the report), `FORECAST_STUDY_EVERY` (a projection every so many games, 4) and `FORECAST_STUDY_KS` (the shrinkages of the layer of each team, 5,20,80).
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { it } from 'vitest'
import { readStudyCompetitions } from './competitions'
import { leaguePaceSlopes, splitHalf, walkForwardProjection } from './projection'
import { formatProjectionSection, type ProjectionCompetition } from './projectionReport'

const OUT = process.env.FORECAST_STUDY_OUT ?? join(process.cwd(), 'test-results', 'projection-study.md')
const EVERY = Number(process.env.FORECAST_STUDY_EVERY ?? 4)
const KS = (process.env.FORECAST_STUDY_KS ?? '5,20,80').split(',').map(Number)

it('evaluates the projection walk-forward over the export and writes the report', () => {
  const results = readStudyCompetitions().map(({ name, gender, games }): ProjectionCompetition => {
    const started = Date.now()
    const result = { name, gender, games: games.length, projection: walkForwardProjection(games, gender, { from: 40, every: EVERY, ks: KS }), slopes: leaguePaceSlopes(games, gender), reliability: splitHalf(games, gender) }
    process.stdout.write(`${name}: ${games.length} games, ${((Date.now() - started) / 1000).toFixed(0)} s\n`)
    return result
  })
  mkdirSync(dirname(OUT), { recursive: true })
  writeFileSync(OUT, `# Evaluación walk-forward de la proyección multifactorial (${new Date().toISOString().slice(0, 10)})\n\n${formatProjectionSection(results)}`, 'utf-8')
  process.stdout.write(`report: ${OUT}\n`)
}, 7_200_000)
