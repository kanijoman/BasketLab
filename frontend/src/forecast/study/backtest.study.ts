// The walk-forward evaluation of the forecast over the real competitions of the local export (#851). Not a test of the CI: run it by hand,
//   python run_local_export.py [--collection NAME ...]      (writes frontend/public/local-data, git-ignored)
//   cd frontend && npm run study:forecast
// and it writes the report to `test-results/forecast-study.md` (git-ignored); the figures that matter are copied to docs/evaluaciones/. Settings (environment): `FORECAST_STUDY_DIR` (the export),
// `FORECAST_STUDY_OUT` (the report), `FORECAST_STUDY_COLLECTIONS` (a comma-separated list of names; by default every FEB league phase with at least `FORECAST_STUDY_MIN_GAMES` games, 100).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { it } from 'vitest'
import type { Competition } from '@/localdata/competition'
import { buildGames } from '../gameLog'
import { formatReport, type CompetitionResult } from './report'
import { walkForwardHeadline, walkForwardPreviews, walkForwardSeason } from './walkForward'

const DIR = process.env.FORECAST_STUDY_DIR ?? join(process.cwd(), 'public', 'local-data')
const OUT = process.env.FORECAST_STUDY_OUT ?? join(process.cwd(), 'test-results', 'forecast-study.md')
const MIN_GAMES = Number(process.env.FORECAST_STUDY_MIN_GAMES ?? 100)

interface Entry { name: string; file: string; league: 'feb' | 'fbcyl'; games: number }

/** The family of a competition by its name (the export does not carry it): the women's leagues are LF Endesa, LF Challenge and L.F.-2. */
const genderOf = (name: string): string => (/^(LF_|L_F_)/.test(name) ? 'F' : 'M')

it('evaluates the forecast walk-forward over the local export and writes the report', () => {
  const entries = (JSON.parse(readFileSync(join(DIR, 'index.json'), 'utf-8')) as { collections: Entry[] }).collections
  const wanted = process.env.FORECAST_STUDY_COLLECTIONS?.split(',').map(s => s.trim())
  const chosen = entries.filter(e => (wanted ? wanted.includes(e.name) : e.league === 'feb' && /liga_regular/i.test(e.name) && e.games >= MIN_GAMES))
  if (!chosen.length) throw new Error(`No competition to evaluate in ${DIR}: export some with run_local_export.py or name them in FORECAST_STUDY_COLLECTIONS.`)
  const results = chosen.map((e): CompetitionResult => {
    const games = buildGames((JSON.parse(readFileSync(join(DIR, e.file), 'utf-8')) as Competition).team_rows)
    const gender = genderOf(e.name)
    const started = Date.now()
    const result = { name: e.name, gender, games: games.length, headline: walkForwardHeadline(games, gender), previews: walkForwardPreviews(games, gender, { from: 40, every: 4 }), season: walkForwardSeason(games, gender) }
    process.stdout.write(`${e.name}: ${games.length} games, ${((Date.now() - started) / 1000).toFixed(0)} s\n`)
    return result
  })
  mkdirSync(dirname(OUT), { recursive: true })
  writeFileSync(OUT, formatReport(results, new Date().toISOString().slice(0, 10)), 'utf-8')
  process.stdout.write(`report: ${OUT}\n`)
}, 3_600_000)
