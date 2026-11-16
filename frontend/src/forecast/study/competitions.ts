// The competitions the studies read (#851, #938): a local export (`python run_local_export.py`, or the published rows written by `python scripts/web_data_dump.py`), an `index.json` with one entry
// per competition and a file with its rows. Settings (environment): `FORECAST_STUDY_DIR` (the export), `FORECAST_STUDY_COLLECTIONS` (a comma-separated list of names; by default every FEB league
// phase with at least `FORECAST_STUDY_MIN_GAMES` games, 100).
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { Competition } from '@/localdata/competition'
import { buildGames, type GameResult } from '../gameLog'

export const STUDY_DIR = process.env.FORECAST_STUDY_DIR ?? join(process.cwd(), 'public', 'local-data')
const MIN_GAMES = Number(process.env.FORECAST_STUDY_MIN_GAMES ?? 100)

interface Entry { name: string; file: string; league: 'feb' | 'fbcyl'; games: number; gender?: string }

export interface StudyCompetition { name: string; gender: string; games: GameResult[] }

/** The family of a competition: the export's when it says it, else by its name (the women's leagues are LF Endesa, LF Challenge and L.F.-2). */
const genderOf = (e: Entry): string => e.gender ?? (/^(LF_|L_F_)/.test(e.name) ? 'F' : 'M')

export function readStudyCompetitions(): StudyCompetition[] {
  const entries = (JSON.parse(readFileSync(join(STUDY_DIR, 'index.json'), 'utf-8')) as { collections: Entry[] }).collections
  const wanted = process.env.FORECAST_STUDY_COLLECTIONS?.split(',').map(s => s.trim())
  const chosen = entries.filter(e => (wanted ? wanted.includes(e.name) : e.league === 'feb' && /liga_regular/i.test(e.name) && e.games >= MIN_GAMES))
  if (!chosen.length) throw new Error(`No competition to evaluate in ${STUDY_DIR}: export some with run_local_export.py or scripts/web_data_dump.py, or name them in FORECAST_STUDY_COLLECTIONS.`)
  return chosen.map(e => ({ name: e.name, gender: genderOf(e), games: buildGames((JSON.parse(readFileSync(join(STUDY_DIR, e.file), 'utf-8')) as Competition).team_rows) }))
}
