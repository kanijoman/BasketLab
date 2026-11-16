// The walk-forward evaluation of the forecast over the real competitions of the local export (#851). Not a test of the CI: run it by hand,
//   python run_local_export.py [--collection NAME ...]      (writes frontend/public/local-data, git-ignored; or python scripts/web_data_dump.py --out DIR, the published rows)
//   cd frontend && npm run study:forecast
// and it writes the report to `test-results/forecast-study.md` (git-ignored); the figures that matter are copied to docs/evaluaciones/. Settings (environment): those of `competitions.ts`
// (`FORECAST_STUDY_DIR`, `FORECAST_STUDY_COLLECTIONS`, `FORECAST_STUDY_MIN_GAMES`), `FORECAST_STUDY_OUT` (the report) and `FORECAST_STUDY_FROM` (the first game previewed, 40; 15 for the
// start of the season, #947).
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { it } from 'vitest'
import { readStudyCompetitions } from './competitions'
import { formatReport, type CompetitionResult } from './report'
import { walkForwardHeadline, walkForwardPreviews, walkForwardSeason } from './walkForward'

const OUT = process.env.FORECAST_STUDY_OUT ?? join(process.cwd(), 'test-results', 'forecast-study.md')
const FROM = Number(process.env.FORECAST_STUDY_FROM ?? 40)

it('evaluates the forecast walk-forward over the local export and writes the report', () => {
  const results = readStudyCompetitions().map(({ name, gender, games }): CompetitionResult => {
    const started = Date.now()
    const result = { name, gender, games: games.length, headline: walkForwardHeadline(games, gender), previews: walkForwardPreviews(games, gender, { from: FROM, every: 4 }), season: walkForwardSeason(games, gender) }
    process.stdout.write(`${name}: ${games.length} games, ${((Date.now() - started) / 1000).toFixed(0)} s\n`)
    return result
  })
  mkdirSync(dirname(OUT), { recursive: true })
  writeFileSync(OUT, formatReport(results, new Date().toISOString().slice(0, 10)), 'utf-8')
  process.stdout.write(`report: ${OUT}\n`)
}, 3_600_000)
